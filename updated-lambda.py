import boto3
import json
import time
import logging
from aws_lambda_powertools.event_handler.api_gateway import (
    ApiGatewayResolver,
    ProxyEventType,
    Response,
)

idc_client = boto3.client('identitystore')
sso_client = boto3.client('sso-admin')
instance_arn = 'arn:aws:sso:::instance/ssoins-712345678567'
idc_id="d-9267420026"
app = ApiGatewayResolver(proxy_type=ProxyEventType.APIGatewayProxyEventV2)
        

def check_status(describe_status,req_id):
    if(describe_status=="create_account_assignment"):
        response = sso_client.describe_account_assignment_creation_status(
            InstanceArn=instance_arn,
            AccountAssignmentCreationRequestId=req_id
        )
        return response
    elif(describe_status=="delete_account_assignment"):
        response = sso_client.describe_account_assignment_deletion_status(
            InstanceArn=instance_arn,
            AccountAssignmentDeletionRequestId=req_id
        )
        return response
    else:
        return None

def getUserId(username):
    try:
        response_user=idc_client.get_user_id(
            IdentityStoreId=idc_id,
            AlternateIdentifier={
                'UniqueAttribute': {
                    'AttributePath': 'emails.value',
                    'AttributeValue': f"{username}"
                }    
        })
        response_status = idc_client.describe_user(
            IdentityStoreId=idc_id,
            UserId=response_user['UserId']
        )
        return response_user 
    except Exception as e:
        return None

def getGroupId(group_name):
    try:
        response_group_id=idc_client.get_group_id(
            IdentityStoreId=idc_id,
            AlternateIdentifier={
                'UniqueAttribute': {
                    'AttributePath': 'displayName',
                    'AttributeValue': f"{group_name}"
                }    
        })
        return response_group_id 
    except Exception as e:
        return None

def getMembershipId(group_id,user_id):
    try:
        response_membership_id=idc_client.get_group_membership_id(
            IdentityStoreId=idc_id,
            GroupId=group_id,
            MemberId={
                'UserId': user_id
        })
        return response_membership_id 
    except Exception as e:
        return None

def sendResponse(status, message):
    if(status=="success"):
        success_response = {
            "statusCode": 200,
            "body": json.dumps({"message": message})
        }
        return Response(status_code=success_response["statusCode"],content_type="application/json",body=success_response["body"])
    else:
        failure_response = {
            "statusCode": 404,
            "body": json.dumps({"message": message})
        }
        return Response(status_code=failure_response["statusCode"],content_type="application/json",body=failure_response["body"])
        


@app.post('/add-permission-to-users') 
def addPermToUser():
    username = app.current_event.get_query_string_value(name="user", default_value=None)
    permission_set_id = app.current_event.get_query_string_value(name="permissionSetArn", default_value=None)
    acc= app.current_event.get_query_string_value(name="account_id", default_value=None)
    if(username is None or permission_set_id is None or acc is None):
        return sendResponse("failure",f"Failed to add username {username}. Error - Expected Values not provided.")
    permission_set_arn = f"arn:aws:sso:::permissionSet/ssoins-79071ef5f2a874d9/{permission_set_id}"
    
    
    response_user=getUserId(username)
    if(response_user is None):
        return sendResponse("failure",f"Failed to add username {username}. Error - User Not found in IdentityCenter. Automation ended in failure.")
        
    
    try:
        response_acc_assign = sso_client.create_account_assignment(
            InstanceArn=instance_arn,
            TargetId=acc,
            TargetType='AWS_ACCOUNT',
            PermissionSetArn=permission_set_arn,
            PrincipalType='USER',
            PrincipalId=response_user['UserId']
        )
        if(response_acc_assign['ResponseMetadata']['HTTPStatusCode']):
            user_assignment_status=response_acc_assign['AccountAssignmentCreationStatus']['Status']
            user_assignment_req_id=response_acc_assign['AccountAssignmentCreationStatus']['RequestId']
            if(user_assignment_status=="FAILED"):
                return Response(status_code=404,content_type="application/json",body=json.dumps(response_acc_assign, default=str))
    
            elif(user_assignment_status=="SUCCEEDED"):
                return Response(status_code=200,content_type="application/json",body=json.dumps(response_acc_assign, default=str))
    
            elif(user_assignment_status=="IN_PROGRESS"):
                retry_count=0
                while retry_count!=5:
                    retry_count+=1
                    time.sleep(2)
                    user_assignment_reponse=check_status("create_account_assignment",user_assignment_req_id)
                    user_assignment_status=user_assignment_reponse['AccountAssignmentCreationStatus']['Status']
                    if(user_assignment_status=="FAILED"):
                        failure_reason=user_assignment_reponse['AccountAssignmentCreationStatus']['FailureReason']
                        return sendResponse("failure",f"Failed to add username. Error - {failure_reason}")
                    elif(user_assignment_status=="SUCCEEDED"):
                        return sendResponse("success",f"User {username} added successfully.")
                            
        return sendResponse("failure",f"Failed to add permission to username. Error - An Error Occurred. Please reach out to CIAS Team")
    except Exception as e:
        return sendResponse("failure",f"Failed to add permission to username. Error - An Error Occurred. Please reach out to CIAS Team - {e}")
        

@app.post('/remove-permission-from-users') 
def removePermFromUser():
    username = app.current_event.get_query_string_value(name="user", default_value=None)
    permission_set_id = app.current_event.get_query_string_value(name="permissionSetArn", default_value=None)
    acc= app.current_event.get_query_string_value(name="account_id", default_value=None)
    
    if(username is None or permission_set_id is None or acc is None):
        return sendResponse("failure",f"Failed to add username {username}. Error - Expected Values not provided.")
        
    
    permission_set_arn = f"arn:aws:sso:::permissionSet/ssoins-79071ef5f2a874d9/{permission_set_id}"
    
    response_user=getUserId(username)
    if(response_user is None):
        return sendResponse("failure",f"Failed to add username {username}. Error - User Not found in IdentityCenter. Automation ended in failure.")

    
    try:
        response_acc_user_delete = sso_client.delete_account_assignment(
            InstanceArn=instance_arn,
            TargetId=acc,
            TargetType='AWS_ACCOUNT',
            PermissionSetArn=permission_set_arn,
            PrincipalType='USER',
            PrincipalId=response_user['UserId']
        )
        if(response_acc_user_delete['ResponseMetadata']['HTTPStatusCode']):
            user_assignment_status=response_acc_user_delete['AccountAssignmentDeletionStatus']['Status']
            user_assignment_req_id=response_acc_user_delete['AccountAssignmentDeletionStatus']['RequestId']
            if(user_assignment_status=="FAILED"):
                return Response(status_code=404,content_type="application/json",body=json.dumps(response_acc_delete, default=str))
    
            if(user_assignment_status=="SUCCEEDED"):
                return Response(status_code=200,content_type="application/json",body=json.dumps(response_acc_delete, default=str))
    
            if(user_assignment_status=="IN_PROGRESS"):
                retry_count=0
                while retry_count!=5:
                    retry_count+=1
                    time.sleep(2)
                    user_delete_response=check_status("delete_account_assignment",user_assignment_req_id)
                    user_assignment_status=user_delete_response['AccountAssignmentDeletionStatus']['Status']
                    if(user_assignment_status=="FAILED"):
                        failure_reason=user_delete_response['AccountAssignmentDeletionStatus']['FailureReason']
                        if("EntitlementItem doesn't exist" in failure_reason):
                            failure_reason = "User was never associated with the policy. Please check the policy and account you want to remove from user. Automation completed"
                        
                        return sendResponse("failure",f"Failed to remove username {username}. Error - {failure_reason}")
                    elif(user_assignment_status=="SUCCEEDED"):
                        return sendResponse("success",f"User {username} removed successfully.")
                            
        return sendResponse("failure",f"Failed to remove permission from username. Error - An Error Occurred. Please reach out to CIAS Team")
    except Exception as e:
        return sendResponse("failure",f"Failed to remove permission from username. Error - An Error Occurred. Please reach out to CIAS Team - {e}")
        


@app.post('/create-idc-group') 
def create_idc_group():
    group_name = app.current_event.get_query_string_value(name="group_name", default_value=None)
    if(group_name is None):
        return sendResponse("failure",f"Failed to create group. Error - Group Name not provided")
    try: 
        response_create_grp = idc_client.create_group(
            IdentityStoreId=idc_id,
            DisplayName=group_name,
            Description=group_name,
        )
        if(response_create_grp['ResponseMetadata']['HTTPStatusCode']==200):
            return sendResponse("success",f"Group {group_name} created successfully.")
    except Exception as e:
        print(e)
        return sendResponse("failure",f"Failed to create group. Please reach out to CIAS Team. Error - {e}")
        


@app.post('/remove-idc-group') 
def remove_idc_group():
    group_name = app.current_event.get_query_string_value(name="group_name", default_value=None)
    if(group_name is None):
        return sendResponse("failure",f"Failed to remove group. Error - Group Name not provided")
    
    response_group_id=getGroupId(group_name)
    if(response_group_id is None):
        return sendResponse("failure",f"Failed to remove group. Error - Group {group_name} not found")
        
    try:
        
        response_delete_grp = idc_client.delete_group(
            IdentityStoreId=idc_id,
            GroupId=response_group_id['GroupId'],
        )
        
        if(response_delete_grp['ResponseMetadata']['HTTPStatusCode']==200):
            return sendResponse("success",f"Group {group_name} deleted successfully.")
            
        return sendResponse("failure",f"Failed to remove group - {group_name}. Please reach out to CIAS Team. {response_delete_grp}")
    except Exception as e:
        print(e)
        return sendResponse("failure",f"Failed to remove group - {group_name}. Please reach out to CIAS Team. Error - {e} ")
    

@app.post('/add-users-to-group') 
def add_user_to_group(): 
    username = app.current_event.get_query_string_value(name="user", default_value=None)
    group_name = app.current_event.get_query_string_value(name="group_name", default_value=None)
    if(username is None or group_name is None):
        return sendResponse("failure",f"Failed to add username to group. Error - Expected Values not provided.")
    response_user=getUserId(username)
    response_group=getGroupId(group_name)
    
    if(response_group is None or response_user is None):
        return sendResponse("failure",f"Failed to add username to group. Error - Group or User not found in IDC.")
    
    try:    
        response_grp_member = idc_client.create_group_membership(
            IdentityStoreId=idc_id,
            GroupId=response_group['GroupId'],
            MemberId={
                'UserId': response_user['UserId']
            }
        )
        if(response_grp_member['ResponseMetadata']['HTTPStatusCode']==200):
            return sendResponse("success",f"User {username} added to group {group_name} successfully")
        
        return sendResponse("failure",f"Failed to add user {username} to group - {group_name}. Please reach out to CIAS Team.")
    except Exception as e:
        print(e)
        return sendResponse("failure",f"Failed to add user {username} to group - {group_name}. Please reach out to CIAS Team. Error - {e} ")
            

@app.post('/remove-user-from-grp') 
def remove_user_from_group():
    username = app.current_event.get_query_string_value(name="user", default_value=None)
    group_name = app.current_event.get_query_string_value(name="group_name", default_value=None)
    if(username is None or group_name is None):
        return sendResponse("failure",f"Failed to add username to group. Error - Expected Values not provided.")
    response_user=getUserId(username)
    response_group=getGroupId(group_name)
    
    if(response_group is None or response_user is None):
        return sendResponse("failure",f"Failed to add username to group. Error - Group or User not found in IDC.")
    
    response_membership_id=getMembershipId(response_group['GroupId'],response_user['UserId'])
    if(response_membership_id is None):
        return sendResponse("failure",f"Failed to add username to group. Error - Group or User not found in IDC.")
    
    try:
        response_remove_membership = idc_client.delete_group_membership(
            IdentityStoreId=idc_id,
            MembershipId=response_membership_id['MembershipId']
        )
        if(response_remove_membership['ResponseMetadata']['HTTPStatusCode']==200):
            return sendResponse("success",f"User {username} removed from group {group_name} successfully")
            
        return sendResponse("failure",f"Failed to remove user {username} from {group_name}. Please reach out to CIAS Team. {response_remove_membership}")
    except Exception as e:
        print(e)
        return sendResponse("failure",f"Failed to remove user {username} from {group_name}. Please reach out to CIAS Team. Error - {e} ")


@app.post('/add-permission-to-grp') 
def addPermToGroup():
    group_name = app.current_event.get_query_string_value(name="group_name", default_value=None)
    permission_set_id = app.current_event.get_query_string_value(name="permissionSetArn", default_value=None)
    acc= app.current_event.get_query_string_value(name="account_id", default_value=None)
    if(group_name is None or permission_set_id is None or acc is None):
        return sendResponse("failure",f"Failed to add group {group_name}. Error - Expected Values not provided.")
    permission_set_arn = f"arn:aws:sso:::permissionSet/ssoins-79071ef5f2a874d9/{permission_set_id}"
    
    
    response_grp=getGroupId(group_name)
    print(response_grp)
    if(response_grp is None):
        return sendResponse("failure",f"Failed to add group {group_name}. Error - Group Not found in IdentityCenter. Automation ended in failure.")
        
    
    try:
        response_acc_assign = sso_client.create_account_assignment(
            InstanceArn='arn:aws:sso:::instance/ssoins-79071ef5f2a874d9',
            TargetId=acc,
            TargetType='AWS_ACCOUNT',
            PermissionSetArn=permission_set_arn,
            PrincipalType='GROUP',
            PrincipalId=response_grp['GroupId']
        )
        if(response_acc_assign['ResponseMetadata']['HTTPStatusCode']):
            user_assignment_status=response_acc_assign['AccountAssignmentCreationStatus']['Status']
            user_assignment_req_id=response_acc_assign['AccountAssignmentCreationStatus']['RequestId']
            if(user_assignment_status=="FAILED"):
                return Response(status_code=404,content_type="application/json",body=json.dumps(response_acc_assign, default=str))
    
            elif(user_assignment_status=="SUCCEEDED"):
                return Response(status_code=200,content_type="application/json",body=json.dumps(response_acc_assign, default=str))
    
            elif(user_assignment_status=="IN_PROGRESS"):
                retry_count=0
                while retry_count!=5:
                    retry_count+=1
                    time.sleep(2)
                    user_assignment_reponse=check_status("create_account_assignment",user_assignment_req_id)
                    user_assignment_status=user_assignment_reponse['AccountAssignmentCreationStatus']['Status']
                    if(user_assignment_status=="FAILED"):
                        failure_reason=user_assignment_reponse['AccountAssignmentCreationStatus']['FailureReason']
                        return sendResponse("failure",f"Failed to add username. Error - {failure_reason}")
                    elif(user_assignment_status=="SUCCEEDED"):
                        return sendResponse("success",f"Group {group_name} added successfully.")
                            
        return sendResponse("failure",f"Failed to add permission to username. Error - An Error Occurred. Please reach out to CIAS Team")
    except Exception as e:
        return sendResponse("failure",f"Failed to add permission to username. Error - An Error Occurred. Please reach out to CIAS Team - {e}")
        

        

def lambda_handler(event, context):
    return app.resolve(event, context)
