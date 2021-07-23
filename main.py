import os
from datetime import datetime, timedelta
from typing import List

import canvasapi
import pytz
import zulip
from canvasapi.assignment import Assignment
from canvasapi.quiz import Quiz

# zulip client configuration
ZULIP_SERVER_URL = os.environ['ZULIP_SERVER_URL']
ZULIP_EMAIL = os.environ['ZULIP_EMAIL']
ZULIP_API_KEY = os.environ['ZULIP_API_KEY']
zuclient = zulip.Client(email=ZULIP_EMAIL, api_key=ZULIP_API_KEY, client="MyTestClient/0.1", site=ZULIP_SERVER_URL)

# canvas client configuration
CANVAS_SERVER_URL = os.environ['CANVAS_SERVER_URL']
CANVAS_API_KEY = os.environ['CANVAS_API_KEY']
canvas = canvasapi.Canvas(base_url=CANVAS_SERVER_URL, access_token=CANVAS_API_KEY)

# course configuration
GROUPS = {
    'prof': {x for x in os.getenv('PROF_EMAILS', '').split(',') if x},
    'ta': {x for x in os.getenv('TA_EMAILS', '').split(',') if x},
    'all': set()
}
REMINDER_GROUPS = [x for x in os.getenv('REMINDER_GROUPS', '').split(',') if x]
CANVAS_COURSE_ID = os.environ['CANVAS_COURSE_ID']
MAX_REMINDER_DAYS = 30
course = canvas.get_course(CANVAS_COURSE_ID)

utc = pytz.UTC
et = pytz.timezone('America/New_York')


def populate_students():
    for user in zuclient.get_users()['members']:
        email = user.get('email')
        if not email:
            continue
        GROUPS['all'].add(email)


def main():
    populate_students()
    message_roles(get_reminder_msg(), REMINDER_GROUPS)


def format_assignment(name, url, due: datetime) -> str:
    days_remaining = (due - datetime.today().replace(tzinfo=et)).days
    due_date = due.date().strftime("%a, %b %d")
    return f'**[{name}]({url}): {due_date}** *({days_remaining} days remaining)*'


def get_reminder_msg():
    min_due = datetime.today().replace(tzinfo=et)
    max_due = (datetime.today() + timedelta(days=MAX_REMINDER_DAYS)).replace(tzinfo=et)
    lines = []
    assignment_lines = []
    quiz_lines = []
    for assignment in course.get_assignments():
        assignment: Assignment
        published = getattr(assignment, 'published', None)
        due = getattr(assignment, 'due_at_date', None)
        url = getattr(assignment, 'html_url', f'{CANVAS_SERVER_URL}courses/{CANVAS_COURSE_ID}/assignments')
        name = getattr(assignment, 'name', 'Untitled Assignment')
        if (not due) or (not published) or (due > max_due) or (due < min_due):
            continue
        due = due.astimezone(et)
        assignment_lines.append(format_assignment(name, url, due))

    for quiz in course.get_quizzes():
        quiz: Quiz
        published = getattr(quiz, 'published', None)
        due = getattr(quiz, 'lock_at_date', None)
        url = getattr(quiz, 'html_url', f'{CANVAS_SERVER_URL}courses/{CANVAS_COURSE_ID}/assignments')
        title = getattr(quiz, 'title', 'Untitled Quiz')
        if (not due) or (not published) or (due > max_due) or (due < min_due):
            continue
        due = due.astimezone(et)
        quiz_lines.append(format_assignment(title, url, due))

    if assignment_lines:
        lines.append('# Upcoming assignments:')
        lines += assignment_lines
    if lines:
        lines.append('')
    if quiz_lines:
        lines.append('# Upcoming quizzes:')
        lines += quiz_lines

    return '\n'.join(lines)


def message_users(msg: str, users: List[str]):
    zuclient.send_message({
        'type': 'private',
        'content': msg,
        'to': users
    })


def message_roles(msg: str, roles: List[str]):
    users = set()
    for role in roles:
        users.update(GROUPS[role])
    message_users(msg, list(users))


if __name__ == '__main__':
    main()
