# AWS-Backup Report in table format in email

This sends a email which will have a backup report as in a tabular formation.

You can add more fields are per your requirenment.

You need to add in line 89, which will be headers(column names)

In the for loop post in like 92 you need to derive your fields and append them in line 111

Note : AWS Lambda does not support tabulate and reportlab by default, you can add a layer, check AWS lambda layer.

Or you can follow the below approach as get the full library and every in local and upload code to AWS Lambda as zip

https://poc2ops.medium.com/serverless-using-python-libraries-that-are-not-part-of-aws-lamba-93aeb6851f72

We will also be using AWS SES service for email delivery, whether you use AWS SES in sandbox or production is up to you.

If you are using 