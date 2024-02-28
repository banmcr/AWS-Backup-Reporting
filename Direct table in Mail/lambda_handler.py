import json
import urllib.parse
import boto3
from tabulate import tabulate
from datetime import datetime, timedelta

def lambda_handler(event, context):
    s3 = boto3.client('s3')
    sns = boto3.client('sns')
    client = boto3.client('backup')
    # TODO implement
    today = datetime.today()
    creation_before = today
    creation_after = today - timedelta(days=1)
    #print(creation_after)
    #print(creation_before)
    response = client.list_report_jobs(
        ByReportPlanName='backup_jobs_report',
        ByCreationBefore=creation_before,
        ByCreationAfter=creation_after,
        )
    #print(response)
    s3_bucket = response['ReportJobs'][0]['ReportDestination']['S3BucketName']
    s3_key = urllib.parse.unquote_plus(response['ReportJobs'][0]['ReportDestination']['S3Keys'][0])
    print(s3_bucket)
    print(s3_key)
    try:
        # Get the JSON file content from S3
        response = s3.get_object(Bucket=s3_bucket, Key=s3_key)
        json_content = response['Body'].read().decode('utf-8')

        # Parse the JSON content
        data = json.loads(json_content)

        # Process the data (you can modify this part based on your needs)
        #print("JSON content:")
        #print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Error reading S3 object: {e}")
        raise e
        
    headers = ["Job Resource", "Job Status", "creationDate", "completionDate"]
    table_data = []
# ...

    for report_item in data.get('reportItems', []):
        job_status = report_item.get('jobStatus', 'N/A')
        job_resource = report_item.get('resourceArn', '').split('/')[-1]
    
        creation_date_str = report_item.get('creationDate', '')
        try:
            creation_date = datetime.strptime(creation_date_str, "%Y-%m-%dT%H:%M:%SZ")
            creation_date_formatted = creation_date.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            creation_date_formatted = creation_date_str
    
        completion_Date_str = report_item.get('completionDate', '')
        try:
            completion_Date = datetime.strptime(completion_Date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            completion_Date_formatted = completion_Date.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            completion_Date_formatted = completion_Date_str
    # Remove the 'Z' character at the end
        if creation_date_formatted.endswith("Z"):
            creation_date_formatted = creation_date_formatted[:-1]
    
        if completion_Date_formatted.endswith("Z"):
            completion_Date_formatted = completion_Date_formatted[:-1]


        table_data.append([job_resource, job_status, creation_date_formatted, completion_Date_formatted])

# ...


    

    col_widths = [20,20,20,20]
    grid_table = tabulate(table_data, headers=headers, tablefmt='presto')
    #html_table = tabulate(table_data, headers=headers, tablefmt='html')
    
    print(grid_table)
    
    grid_sns_message = f"\n\nAWS Backup report \n\n '{grid_table}' \n\nRegards,\nAWS-Team"
    sns_topic_arn = 'arn:aws:sns:ap-south-1:333344455566:AWS-Backup-Topic'
    subject = 'Backup Job Status Report'
    sns.publish(TopicArn=sns_topic_arn, Subject=subject, Message=grid_sns_message)
    
    '''
    html_sns_message = f"<html><body><p>{html_table}</p></body></html>"
    '''
    