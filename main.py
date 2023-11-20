import asyncio
import hashlib
import logging
import os
import sys

import requests
import yaml
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Bot

# Configure logging
logging.basicConfig(filename='./app.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s:%(message)s')

# Load Telegram credentials from .env file
load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHANNEL = os.getenv('TELEGRAM_CHANNEL')  # Telegram channel ID

# Website to monitor
COURSE_URL = 'https://hacker-school.de/unterstuetzen/inspirer/checkin-inspirer-yourschool/?formats%5B%5D=ys'

bot = Bot(token=TELEGRAM_TOKEN)


async def post_new_courses(new_courses):
    """ Post new courses to the Telegram channel. """
    for course in new_courses:
        message = f"New course available:\n\n{course['title']}\n{course['date']}\n\nCheck it out at {COURSE_URL}"
        try:
            await bot.send_message(chat_id=TELEGRAM_CHANNEL, text=message)
            escaped_message = message.replace("\n", "\\n")
            logging.info("Message sent: %s", escaped_message)
        except Exception as e:
            logging.error("Error: %s", e)
            sys.exit(1)


def load_existing_courses():
    """ Load existing courses from a YAML file. """
    if os.path.exists('courses.yml'):
        with open('courses.yml', 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    return []


def save_courses(courses):
    """ Save current courses to a YAML file. """
    with open('courses.yml', 'w', encoding='utf-8') as file:
        yaml.dump(courses, file)


def get_courses():
    """ Find out number of pages and get all courses. """
    try:
        response = requests.get(COURSE_URL, timeout=10)
    except Exception as e:
        logging.error("Error fetching courses: %s", e)
        sys.exit(1)
    soup = BeautifulSoup(response.text, 'html.parser')
    pagination_container = soup.find('ul', class_='pagination')
    if pagination_container:
        pagination_items = pagination_container.find_all('li')
    else:
        logging.error("Pagination container not found")
        return []

    # get first page with previous response to avoid another request
    courses = get_course_page(1, response)

    # last page number is number of items - 2 to remove the next and previous buttons
    last_page = len(pagination_items) - 2
    if last_page < 2:
        return courses
    for page in range(2, last_page+1):
        courses += get_course_page(page)

    return courses


def get_course_page(page_number, page=None):
    """ Get a specific page of courses. """
    if page is None:
        try:
            page = requests.get(
                f"{COURSE_URL}&event_page={page_number}", timeout=10)
        except Exception as e:
            logging.error("Error fetching courses: %s", e)
            sys.exit(1)
    soup = BeautifulSoup(page.text, 'html.parser')
    course_elements = soup.find_all('div', class_='hs-event')

    courses = []
    for course in course_elements:
        courses.append(parse_course(course))

    return courses


def parse_course(course):
    """ Parse a course element and return the details. """

    title = course.find('h3', class_='hs-event-titel').text.strip()
    date = course.find(
        'div', class_='hs-dates').span.find_next_sibling().text.strip()
    # not a bug the element is spelled wrong
    description = course.find(
        'span', class_='hs-curse-discription').text.strip()

    unique_string = title + date + description
    course_id = hashlib.md5(unique_string.encode()).hexdigest()

    course_info = {
        'id': course_id,
        'title': title,
        'date': date,
        'description': description
    }
    return course_info


def main():
    """ Main function to run the course update check and notification. """
    logging.info("Running!")
    existing_courses = load_existing_courses()
    current_courses = get_courses()
    loop = asyncio.get_event_loop()
    new_courses = []

    for e in current_courses:
        if not any(e["id"] == f["id"] for f in existing_courses):
            new_courses.append(e)

    if new_courses:
        loop.run(post_new_courses(new_courses))
        save_courses(current_courses)
        logging.info("New courses found and posted.")
    else:
        logging.info("No new courses found.")


if __name__ == '__main__':
    main()
