import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict

import canvasapi
import pytz
import zulip
from canvasapi.assignment import Assignment
from canvasapi.module import Module, ModuleItem
from canvasapi.user import User
from jinja2 import Environment, select_autoescape, FileSystemLoader

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
GRADEBOOK_CSV = os.environ['GRADEBOOK_CSV']
course = canvas.get_course(CANVAS_COURSE_ID)
# quizzes: List[Quiz] = list(course.get_quizzes())
assignments: List[Assignment] = list(course.get_assignments())
video_lectures_module: Module = next(x for x in course.get_modules() if x.name == "Video Lectures")
video_lectures: List[ModuleItem] = list(video_lectures_module.get_module_items())
# 14. Solution to blah -> Solution to blah
for video_lecture in video_lectures:
    if video_lecture.title[0].isdigit():
        video_lecture.title = video_lecture.title.split('.', 1)[-1].strip()

# template configuration
RAW_RESOURCES = json.loads(os.getenv('RESOURCES', '[]'))
TEMPLATES_DIR = "templates"
templates = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape()
)
reminder_template = templates.get_template("reminder.md")

utc = pytz.UTC
et = pytz.timezone('America/New_York')


@dataclass
class Resource:
    text: str
    link: Optional[str] = None


@dataclass
class Homework:
    name: str
    url: str
    due_date: str
    days_remaining: int
    solution: Optional[Resource] = None


# RESOURCES = [Resource(x['text'], x.get('link')) for x in RAW_RESOURCES]
# Hardcoded for now
RESOURCES = [
    Resource('Need help? Click here to join the office hours from 7:00-8:00PM Mon-Fri',
             'https://meet.google.com/umd-wuvj-sno'),
    Resource('Watch the lecture videos here', 'https://uncc.instructure.com/courses/151666/modules/553666')
]

STU_ID_TO_STU_SIS_ID = {}
with open(GRADEBOOK_CSV) as f:
    reader = csv.reader(f)
    cols = next(reader)
    id_idx = cols.index('ID')
    sis_id_idx = cols.index('SIS Login ID')
    # Skip point info
    next(reader)
    for row in reader:
        STU_ID_TO_STU_SIS_ID[int(row[id_idx])] = row[sis_id_idx].lower()
STU_SIS_ID_TO_STU_ID = {value: key for key, value in STU_ID_TO_STU_SIS_ID.items()}


def get_email(user: User) -> str:
    try:
        return STU_ID_TO_STU_SIS_ID[user.id] + '@uncc.edu'
    except KeyError:
        return None


def get_user(email: str) -> User:
    if not email.endswith("uncc.edu"):
        return None
    stu_sis_id = email.split("@")[0].lower()
    try:
        return course.get_user(STU_SIS_ID_TO_STU_ID[stu_sis_id])
    except KeyError:
        return None


def populate_all():
    for user in zuclient.get_users()['members']:
        email = user.get('email')
        if not email:
            continue
        GROUPS['all'].add(email)


ASSIGNMENT_VIDEOS: Dict[int, List[Resource]] = {}


def pair_videos_to_assignments():
    for assignment in assignments:
        ASSIGNMENT_VIDEOS[assignment.id] = []
        for video in video_lectures:
            if not video.published:
                continue
            if not hasattr(video, "html_url"):
                continue

            if is_pair(assignment, video):
                print((assignment.name, video.title))
                resource = Resource(video.title, video.html_url)
                ASSIGNMENT_VIDEOS[assignment.id].append(resource)


def is_pair(assignment: Assignment, video: ModuleItem):
    name_1 = assignment.name
    name_2 = video.title

    # For now, only pair solution videos
    if "Solution" not in name_2:
        return False

    if name_1.startswith("Assignment") and "-" in name_1:
        name, part = name_1.split("-", 1)
        name = name.strip()
        if name not in name_2:
            return False
        part = part.replace("Part ", "").strip()
        if "Part" in name_2:
            return f"Part {part}" in name_2
        return True
    return False


submissions = {}


def get_submissions(quiz):
    if quiz.id not in submissions:
        submissions[quiz.id] = list(quiz.get_submissions())
    return submissions[quiz.id]


def get_unfinished_assignments(user):
    today = datetime.today().replace(tzinfo=et)
    max_due = (datetime.today() + timedelta(days=MAX_REMINDER_DAYS)).replace(tzinfo=et)
    upcoming_assignments = []
    overdue_assignments = []
    for assignment in assignments:
        assignment: Assignment
        published = getattr(assignment, 'published', None)
        due = getattr(assignment, 'due_at_date', None)
        url = getattr(assignment, 'html_url', f'{CANVAS_SERVER_URL}courses/{CANVAS_COURSE_ID}/assignments')
        name = getattr(assignment, 'name', 'Untitled Assignment')
        if (not due) or (not published) or (due > max_due):
            continue
        user_submission = assignment.get_submission(user)
        if user_submission.submitted_at:
            continue
        due = due.astimezone(et)
        due_date_str, days_remaining = process_date(due)
        videos = ASSIGNMENT_VIDEOS.get(assignment.id, [])
        solution = videos[0] if videos else None
        hw = Homework(name, url, due_date_str, days_remaining, solution)
        if due < today:
            overdue_assignments.append(hw)
        else:
            upcoming_assignments.append(hw)

    # TODO: Quizzes are also assignments apparently so this isn't needed?
    # for quiz in quizzes:
    #     quiz: Quiz
    #     published = getattr(quiz, 'published', None)
    #     due = getattr(quiz, 'lock_at_date', None)
    #     url = getattr(quiz, 'html_url', f'{CANVAS_SERVER_URL}courses/{CANVAS_COURSE_ID}/assignments')
    #     title = getattr(quiz, 'title', 'Untitled Quiz')
    #     if (not due) or (not published) or (due > max_due):
    #         continue
    #     user_submission = next((x for x in get_submissions(quiz) if x.user_id == user.id), None)
    #     if user_submission:
    #         continue
    #     due = due.astimezone(et)
    #     due_date_str, days_remaining = process_date(due)
    #     hw = Homework(title, url, due_date_str, days_remaining)
    #     if due < today:
    #         overdue_assignments.append(hw)
    #     else:
    #         upcoming_assignments.append(hw)
    return upcoming_assignments, overdue_assignments


def main():
    populate_all()
    pair_videos_to_assignments()
    students = []
    for email in GROUPS['all']:
        if email.endswith("@uncc.edu"):
            students.append(email)

    for email in students:
        user = get_user(email)
        if not user:
            continue

        upcoming, overdue = get_unfinished_assignments(user)

        # Only send out reminders to students with overdue assignments
        if not overdue:
            continue

        reminder = get_reminder_msg(upcoming, overdue, RESOURCES)
        message_users(reminder, list(GROUPS['ta'] | GROUPS['prof']))

        # TODO: Uncomment to actually send to students
        # message_users(reminder, list(GROUPS['ta'] | GROUPS['prof'] | {email}))


def process_date(due: datetime) -> Tuple[str, int]:
    days_remaining = (due - datetime.today().replace(tzinfo=et)).days
    due_date = due.date().strftime("%a, %b %d")
    return due_date, days_remaining


def get_reminder_msg(upcoming: List[Homework], overdue: List[Homework], resources: List[Resource]):
    return reminder_template.render(
        upcoming_assignments=upcoming,
        overdue_assignments=overdue,
        resources=resources
    )


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
