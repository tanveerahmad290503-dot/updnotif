from .services import get_gmail_service


def start_gmail_watch(user):

    service = get_gmail_service(user)

    request = {

        "labelIds": ["INBOX"],

        "topicName":

"projects/gmailapi-486910/topics/gmail-push-topic",

    }

    service.users().watch(

        userId="me",

        body=request

    ).execute()