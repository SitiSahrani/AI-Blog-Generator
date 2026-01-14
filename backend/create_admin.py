import os
from django.contrib.auth import get_user_model

def run():
    User = get_user_model()

    username = os.environ.get("ADMIN_USERNAME")
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")

    if not username or not password:
        print("ADMIN env not set")
        return

    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        print("Superuser created")
    else:
        print("Superuser already exists")
