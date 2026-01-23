# ![Image](https://github.com/user-attachments/assets/47bd3819-8d4e-4e3e-82e6-b63ee9b66c3b)

This library will help you interact with your Magister account using python!

## Disclaimer:

Please note: Using unauthorized APIs to access Magister might be against Magister’s Terms of Service.
By using this library, you assume all responsibility and accept any risks associated with breaching these terms.
For more details, please refer to Magister's Terms of Service. (https://magister.nl/over-ons/juridische-zaken/)

## Installation

```
pip install git+https://github.com/H3LL0U/MagisterPy.git
```

or

```
pip install MagisterPy
```

## Contributing

Feel free to create an issue if something doesn't work. It's only been tested on at least 2 schools so far so it is to be expected. If you want to help add a feature it would be great as well! :D
Also please create an issue if you have any questions!

## Basic usage

The following code snippet demonstrates how to authenticate and retrieve your grades, schedule, and messages:

```python
import asyncio
from MagisterPy import MagisterClient
from MagisterPy.auth import MagisterAuth

async def main():
    school_url = "https://school.magister.net"
    username = "your_username"
    password = input("Enter Password: ")

    auth = MagisterAuth(school_url, username, password)
    token = await auth.get_token()

    async with MagisterClient(school_url, token) as client:
        grades = await client.get_grades(limit=5)
        for grade in grades:
            print(f"{grade.subject.description}: {grade.value}")

        folders = await client.get_folders()
        for folder in folders:
            print(f"{folder.name}: {folder.unread_count} unread")

        assignments = await client.get_assignments(open_only=True)
        for assignment in assignments:
            print(f"Due {assignment.deadline}: {assignment.title}")

asyncio.run(main())
```

With MagisterPy, you can access and manage your Magister account directly from Python, automating repetitive tasks and integrating your school data into your projects.
