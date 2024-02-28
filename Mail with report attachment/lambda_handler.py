import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import json
import urllib.parse
import boto3
from tabulate import tabulate
from datetime import datetime
import datetime
from io import BytesIO
from botocore.exceptions import NoCredentialsError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

def get_instance_backup_info(backup_job):
    backup_info = {
        'private_ip': 'N/A',
        'backup_size_gb': 'N/A'
    }

    ec2_client = boto3.client('ec2')

    try:
        resource_arn = backup_job.get("ResourceArn", "")
        print(f"ResourceArn: {resource_arn}")

        # Check if resource_arn is not empty before attempting to split
        if resource_arn:
            # Get private IP
            response = ec2_client.describe_instances(InstanceIds=[resource_arn.split(':')[-1].split('/')[1]])
            instances = response.get('Reservations', [])[0].get('Instances', []) if 'Reservations' in response else []

            # Use a concise if-else structure to set private_ip
            backup_info['private_ip'] = instances[0]['PrivateIpAddress'] if instances else 'N/A'

        # Get backup size from the backup job, checking for variations in the data structure
        size_attributes = ['ResourceSizeInBytes', 'BackupSizeBytes', 'BackupSizeInBytes', 'CalculatedLifecycleBytes', 'RecoveryPointCreatorBackupSizeBytes']
        for attr in size_attributes:
            if attr in backup_job:
                backup_size_bytes = backup_job[attr]
                # Converting bytes to gigabytes
                backup_info['backup_size_gb'] = round(backup_size_bytes / (1024**3), 2)
                break  # Break out of the loop if a valid attribute is found

    except Exception as e:
        print(f"Error retrieving backup information for resource {resource_arn}: {e}")

    return backup_info





def lambda_handler(event, context):
    #sns = boto3.client('sns')
    backupclient = boto3.client('backup')
    
    current_date = datetime.datetime.now()

    # Calculate the first day of the current month
    first_day_current_month = current_date.replace(day=1)

    # Calculate the last day of the previous month
    last_day_previous_month = first_day_current_month - datetime.timedelta(days=1)
    last_day_previous_month = last_day_previous_month.replace(hour=23, minute=59, second=59, microsecond=0)

    # Calculate the first day of the previous month
    first_day_previous_month = last_day_previous_month.replace(day=1)
    first_day_previous_month = first_day_previous_month.replace(hour=0, minute=0, second=0, microsecond=0)

    # Print the results
    print("Current Month:", current_date.strftime("%B %Y"))
    print("First Day of Previous Month:", first_day_previous_month.strftime("%Y-%m-%d"))
    print("Last Day of Previous Month:", last_day_previous_month.strftime("%Y-%m-%d"))
    
    response = backupclient.list_backup_jobs(
            MaxResults=500,
            ByState='COMPLETED',
            ByCreatedBefore=last_day_previous_month,
            ByCreatedAfter=first_day_previous_month,
    )
    print("below is the response")
    print(response)

    headers = ["BackupJobID","Job Status", "ResourceType", "ResourceName", "completionDate","Instance Private IP","Backup Size (GB)"]
    table_data = []
    
    for backup_job in response["BackupJobs"]:
        backup_job_id = backup_job["BackupJobId"]
        state = backup_job["State"]
        resource_type = backup_job["ResourceType"]
        resource_name = backup_job["ResourceName"]
        creationDate = backup_job["CreationDate"]
        completionDate = backup_job["CompletionDate"]

        #resource_id = backup_job["ResourceArn"].split(':')[-1].split('/')[1]
        if resource_type == 'RDS':
        # For RDS instances, resource_id is the same as resource_name
            resource_id = resource_name
        elif '/' in backup_job.get("ResourceArn", ""):
        # For other instances with "/" in ResourceArn
            resource_id = backup_job.get("ResourceArn", "").split(':')[-1].split('/')[1]
        else:
        # For any other cases, set resource_id to "N/A"
            resource_id = "N/A"
        instance_info = get_instance_backup_info(backup_job)
        table_data.append([backup_job_id, state, resource_type, resource_name,resource_id, creationDate,completionDate,instance_info['private_ip'], instance_info['backup_size_gb']])

    grid_table = tabulate(table_data, headers=headers, tablefmt='pretty')
    #html_table = tabulate(table_data, headers=headers, tablefmt='html')
    
    #print(grid_table)
    
    #grid_sns_message = f"\n\nAWS Backup report \n\n '{grid_table}' \n\nRegards,\nAWS-Team"
    #sns_topic_arn = 'arn:aws:sns:ap-south-1:22233344455:Bakup-alerts'
    subject = 'Backup Job Status Report'
    #sns.publish(TopicArn=sns_topic_arn, Subject=subject, Message=grid_sns_message)

    ###########################PDF Creation ###########################
    output_filename = "/tmp/Monthly-Backup-Report.pdf"

    pdf_document = SimpleDocTemplate(output_filename, pagesize=(1000, 500))
    styles = getSampleStyleSheet()
    # Create a list to hold the flowables (elements) in the document
    elements = []

    # Add a title
    first_day_str = first_day_previous_month.strftime("%d-%m-%Y")
    last_day_str = last_day_previous_month.strftime("%d-%m-%Y")
    title_text = f"Backup Jobs Report from {first_day_str} to {last_day_str}"
    title = Paragraph(title_text, styles['Title'])
    elements.append(title)

    # Create a Table element from the data
    table_data.insert(0, ["BackupJobID", "Job Status", "ResourceType", "ResourceName", "ResourceID", "Creation Date", "Completion Date", "private_ip", "Backup Size (GB)"])  # Insert headers
    pdf_table = Table(table_data)

    # Apply styles to the table
    style = TableStyle([('BACKGROUND', (0, 0), (-1, 0), '#77aaff'),
                        ('TEXTCOLOR', (0, 0), (-1, 0), 'white'),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('GRID', (0, 0), (-1, -1), 1, 'black'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8)])

    pdf_table.setStyle(style)
    elements.append(pdf_table)

    # Build the PDF document with the elements
    pdf_document.build(elements)
    ###################################################################
    ########################## SEND - EMAILS ##########################
    to_email_env = os.environ.get('toEmail')
    if to_email_env:
        # Split the comma-separated values into a list
        to_emails = to_email_env.split(',')
    sender_email = os.environ['sender_email']
    aws_region = os.environ['ses_aws_region']
    subject = "ESAF Monthly Backup Mail Report"
    body = f"Hi,\nPlease find below report for AWS Backup Jobs Report from {first_day_str} to {last_day_str} \n\nRegards\nC4CAWS-Team"
    #to_emails = ['banmcr@gmail.com']
    attachment_path = "/tmp/Monthly-Backup-Report.pdf"
    ses = boto3.client('ses', region_name=aws_region)
    # Create a MIME message
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = ", ".join(to_emails)

    # Attach the body of the email
    msg.attach(MIMEText(body, 'plain'))
     # Attach the file
    attachment_filename = os.path.basename(attachment_path)
    attachment = open(attachment_path, "rb")
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f"attachment; filename= {attachment_filename}")
    msg.attach(part)

    try:
        response = ses.send_raw_email(
            Source=sender_email,
            Destinations=to_emails,
            RawMessage={'Data': msg.as_string()}
        )
        print("Email sent successfully:", response)
    except NoCredentialsError as e:
        print(f"Failed to send email. Error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    lambda_handler({},{})