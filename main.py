from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json
import os
import base64
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re


def extract_passenger_details(soup):
    tags = soup.find_all('div')
    passenger_details_div = [
        div for div in tags if div.get_text().strip() == 'Passenger Details']
    passenger_table = passenger_details_div[0].find_next('table')
    if passenger_table:
        header_row = passenger_table.find('tr')
        column_names = [header.text.strip()
                        for header in header_row.find_all('td')]
        passenger_rows = passenger_table.find_all(
            'tr')[1:]  # Exclude the header row
        passengers = []
        for row in passenger_rows:
            passenger_data = [cell.text.strip() for cell in row.find_all('td')]
            passengers.append(passenger_data)
        return [column_names, passengers]
    else:
        print('Passenger table not found next to the specified div.')
    return []  # Return an empty list if no passengers were found

def extract_general_details(soup):
    tags = soup.find_all('span')
    booking_details_span = [span for span in tags if span.get_text().strip(
    ) == "Thank you for using IRCTC's online rail reservation facility. Your booking details are indicated below."]
    details_table = booking_details_span[0].find_next('table')
    if(details_table):
        details_map = {}
        details_list = details_table.find_all('td')
        i = 0
        while(i < len(details_list)):
            key = re.sub(r':\s*', '', details_list[i].get_text()).strip()
            value = details_list[i+1].get_text().strip()
            if(key.strip() != ''):
                details_map[key] = value
            i += 2

    return details_map

def generate_event_description(passenger_list,train_details):
    description = 'Train Details:\n\n'
    description += f'- Train No: {train_details["Train No. / Name"]}\n'
    description += f'- Quota: {train_details["Quota"]}\n'

    description += f'Passengers:\n\n'
    for passenger in passenger_list:
        description += f'- Sl. No.: {passenger[0]}\n'
        description += f'  Name: {passenger[1]}\n'
        description += f'  Age: {passenger[2]}\n'
        description += f'  Gender: {passenger[3]}\n'
        description += f'  Status: {passenger[4]}\n'
        description += f'  Coach: {passenger[5]}\n'
        description += f'  Seat / Berth / WL No: {passenger[6]}\n\n'
    return description

def generate_event(passenger_list, train_details, email_address):
    try:
        description = generate_event_description(passenger_list[1],train_details)
        departure_datetime = datetime.strptime(train_details['Scheduled Departure*'], '%d-%b-%Y %H:%M')
        arrival_datetime = datetime.strptime(train_details['Scheduled Arrival'], '%d-%b-%Y %H:%M')
        # print("-------- Departure Date : ", departure_datetime)
        # print("-------- Arrival Date : ", arrival_datetime)
        # Calculate the reminder time (9 PM on the previous day)
        test_time = (departure_datetime - timedelta(days=1)).replace(hour=18, minute=56)
        alarm1 = departure_datetime.replace(hour=5, minute=0)
        alarm2 = departure_datetime.replace(hour=5, minute=30)
        alarm3 = departure_datetime.replace(hour=6, minute=0)
        alarm4 = departure_datetime.replace(hour=6, minute=15)
        alarm5 = departure_datetime.replace(hour=6, minute=30)

        event = {
            'summary': f"IRCTC Ticket : (PNR : {train_details['PNR No.']})",
            'description': description,
            'start': {
                'dateTime': departure_datetime.isoformat(),
                'timeZone': 'Asia/Kolkata',  # Set to Indian Standard Time (IST)
            },
            'end': {
                'dateTime': arrival_datetime.isoformat(),
                'timeZone': 'Asia/Kolkata',  # Set to Indian Standard Time (IST)
            },
            'startLocation': train_details["From"],
            'endLocation': train_details["To"],
            # 'attendees': [
            #     {'email': email_address, 'notification': {'method': 'popup', 'minutes': remainder_time}},
            # ],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': (departure_datetime - alarm1).total_seconds() // 60},
                    {'method': 'popup', 'minutes': (departure_datetime - alarm2).total_seconds() // 60},
                    {'method': 'popup', 'minutes': (departure_datetime - alarm3).total_seconds() // 60},
                    {'method': 'popup', 'minutes': (departure_datetime - alarm4).total_seconds() // 60},
                    {'method': 'popup', 'minutes': (departure_datetime - alarm5).total_seconds() // 60},
                    # {'method': 'popup', 'minutes': (departure_datetime - test_time).total_seconds() // 60},
                ]
            }
        }
    except:
        print("-------- Error in generating event")
        event = False
    return event

def if_travel_date_in_future(details):
    date_of_boarding_str = details['Date Of Boarding']
    date_of_boarding = datetime.strptime(
        date_of_boarding_str, '%d-%b-%Y').date()
    if date_of_boarding > datetime.now().date():
        # print("-------- Date Of Boarding : ", date_of_boarding)
        details['Date Of Boarding'] = date_of_boarding
        return True
    return False

def does_irctc_event_notification_exist_for_date(event, train_details):
    pattern = f"IRCTC Ticket : (PNR : {train_details['PNR No.']})"
    if(pattern in event['summary']):
        if(datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date'))).date() == train_details['Date Of Boarding']):
            return True
    return False

def load_credentials(credentials_file, oauth_token_file, scopes):
    if os.path.isfile(oauth_token_file):
        # If the token file exists, load the credentials from it
        with open(oauth_token_file, 'r') as token_file:
            token_data = json.load(token_file)
        credentials = Credentials.from_authorized_user_info(token_data)
    else:
        # If the token file does not exist, perform the OAuth flow to get the credentials
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_file, scopes)
        credentials = flow.run_local_server(port=0)

        # Save the credentials to the token file for future use
        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
            'expiry': credentials.expiry.isoformat()
        }
        with open(oauth_token_file, 'w') as token_file:
            json.dump(token_data, token_file)

    return credentials

def load_credentials_github(token_data, scopes):
    token_data = json.loads(token_data)
    credentials = Credentials.from_authorized_user_info(token_data)
    return credentials

def fetch_emails(credentials, email_address, query, subject_str):
    # Create an instance of the Gmail API client
    gmail_service = build('gmail', 'v1', credentials=credentials)

    # Fetch a list of email IDs matching the specified query
    response = gmail_service.users().messages().list(
        userId=email_address, q=query, maxResults=25).execute()
    messages = response.get('messages', [])

    emails = []
    # Iterate over the retrieved email IDs and fetch the corresponding email content
    for message in messages:
        # Fetch the full email message
        email = gmail_service.users().messages().get(
            userId=email_address, id=message['id']).execute()
        # Extract the subject and timestamp of the email
        timestamp = int(email['internalDate']) / \
            1000 if 'internalDate' in email else 0
        body = email.get('payload', {}).get('body', []).get('data', [])
        subject = ''
        headers = email.get('payload', {}).get('headers', [])
        for header in headers:
            if header['name'] == 'Subject':
                subject = header['value']
                break

        # Convert the timestamp to a date format
        date = datetime.fromtimestamp(
            timestamp).strftime('%Y-%m-%d %H:%M:%S')

        # Decode and append the email details to the list
        decoded_body = base64.urlsafe_b64decode(body).decode('utf-8')
        if(subject_str in subject):
            emails.append({
                'date': date,
                'body': decoded_body
            })

    return emails

def fetch_create_irctc_events(credentials, calendar_id, calendar_notifications, email_address):
    # Load API credentials

    calendar_service = build('calendar', 'v3', credentials=credentials)

    # Call the Calendar API
    now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    events_result = calendar_service.events().list(
        calendarId=calendar_id,
        timeMin=now,
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    if not events:
        print('No upcoming events found.')

    irctc_events = [ event for event in events if 'IRCTC' in event.get('summary', '')]

    for train_details, passenger_details in calendar_notifications:
        event_exists = any(
            does_irctc_event_notification_exist_for_date(event, train_details)
            for event in irctc_events
        )
        
        if event_exists:
            pass
            # print("-------- Event already exists for date:", train_details['Date Of Boarding'])
        else:
            irctc_event = generate_event(passenger_details, train_details, email_address)
            if(irctc_event):
                success = calendar_service.events().insert(calendarId=calendar_id, sendNotifications=True, body=irctc_event).execute()
            # print('Event created:', success['id'])

# Main execution


def main():
    credentials_file = 'credentials.json'
    oauth_token_file = 'token.json'
    scopes = ['https://www.googleapis.com/auth/gmail.readonly',
              'https://www.googleapis.com/auth/calendar']

    # Load credentials
    # credentials = load_credentials(credentials_file, oauth_token_file, scopes)
    credentials = load_credentials_github(os.environ["TOKEN"], scopes)
    # The email address from which you want to fetch and read emails
    email_address = os.environ["IRCTC_TICKET_USER_EMAIL"]

    # Fetch emails
    query = f"to:{email_address} from:ticketadmin@irctc.co.in"
    emails = fetch_emails(credentials, email_address,
                          query, 'Booking Confirmation')

    calendar_notifications = []
    for email in emails:
        soup = BeautifulSoup(email['body'], 'html.parser')
        general_details = extract_general_details(soup)
        if if_travel_date_in_future(general_details):
            passenger_details = extract_passenger_details(soup)
            calendar_notifications.append((general_details, passenger_details))

    fetch_create_irctc_events(
        credentials, 'primary', calendar_notifications, email_address)


if __name__ == '__main__':
    main()
