import boto3
import json
import time
import logging
from aws_lambda_powertools.event_handler.api_gateway import (
    ApiGatewayResolver,
    ProxyEventType,
    Response,
)

client = boto3.client('identitystore')
sso_client = boto3.client('sso-admin')
instance_arn = 'arn:aws:sso:::instance/ssoins-698759770ce5a35e'
app = ApiGatewayResolver(proxy_type=ProxyEventType.APIGatewayProxyEventV2)
        

def check_status(sso_client,describe_status,req_id):
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
    idc = boto3.client('identitystore')
    try:
        response_user=idc.get_user_id(
            IdentityStoreId='d-996707e2f3',
            AlternateIdentifier={
                'UniqueAttribute': {
                    'AttributePath': 'emails.value',
                    'AttributeValue': f"{username}"
                }    
        })
        return response_user 
    except Exception as e:
        print(e)
        return Response(status_code=500,content_type="application/json",body="User Not found in IdentityCenter. Automation ended in failure.")
       
    

@app.post('/add-permission') 
def addPermToUser():
    post_data = app.current_event.json_body
    print(post_data)
    username = post_data.get("user", None)
    permission_set_arn = post_data.get("permissionSetArn", None)
    acc= post_data.get("account_id", None)

    sso_client = boto3.client('sso-admin')
    
    response_user=getUserId(username)
    
    try:
        response_acc_assign = sso_client.create_account_assignment(
            InstanceArn='arn:aws:sso:::instance/ssoins-698759770ce5a35e',
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
                    user_assignment_reponse=check_status(sso_client,"create_account_assignment",user_assignment_req_id)
                    user_assignment_status=user_assignment_reponse['AccountAssignmentCreationStatus']['Status']
                    if(user_assignment_status=="FAILED"):
                        failure_reason=user_assignment_reponse['AccountAssignmentCreationStatus']['FailureReason']
                        success_response = {
                            "statusCode": 404,
                            "body": json.dumps({"message": f"Failed to add username. Error - {failure_reason}"})
                        }
                        return Response(status_code=success_response["statusCode"],content_type="application/json",body=success_response["body"])
                    if(user_assignment_status!="SUCCEEDED"):
                        success_response = {
                            "statusCode": 200,
                            "body": json.dumps({"message": f"User {username} added successfully."})
                        }
                        return Response(status_code=success_response["statusCode"],content_type="application/json",body=success_response["body"])
                            
        return Response(status_code=500,content_type="application/json",body="An Error Occurred. Please reach out to IAM")
    except Exception as e:
        print(e)
        return Response(status_code=500,content_type="application/json",body="Something went wrong. Automation ended in failure.")
        

@app.post('/remove-permission') 
def removePermFromUser():
    try:
        post_data = app.current_event.json_body
        username = post_data.get("user", None)
        permission_set_arn = post_data.get("permissionSetArn", None)
        acc= post_data.get("account_id", None)
        
        response_user=getUserId(username)
        sso_client = boto3.client('sso-admin')
    
        response_acc_user_delete = sso_client.delete_account_assignment(
            InstanceArn='arn:aws:sso:::instance/ssoins-698759770ce5a35e',
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
                    user_delete_reponse=check_status(sso_client,"delete_account_assignment",user_assignment_req_id)
                    user_assignment_status=user_delete_reponse['AccountAssignmentDeletionStatus']['Status']
                    if(user_assignment_status=="FAILED"):
                        failure_reason=user_delete_reponse['AccountAssignmentDeletionStatus']['FailureReason']
                        success_response = {
                            "statusCode": 404,
                            "body": json.dumps({"message": f"Failed to remove username {username}. Error - {failure_reason}"})
                        }
                        return Response(status_code=success_response["statusCode"],content_type="application/json",body=success_response["body"])
                    if(user_assignment_status=="SUCCEEDED"):
                        success_response = {
                            "statusCode": 200,
                            "body": json.dumps({"message": f"User {username} removed successfully."})
                        }
                        return Response(status_code=success_response["statusCode"],content_type="application/json",body=success_response["body"])
                            
        return Response(status_code=500,content_type="application/json",body="An Error Occurred. Please reach out to IAM")
    except Exception as e:
        print(e)
        return Response(status_code=500,content_type="application/json",body="Something went wrong. Automation ended in failure. Reach out to IAM")
        

def lambda_handler(event, context):
    return app.resolve(event, context)