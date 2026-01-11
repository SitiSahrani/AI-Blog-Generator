import json
import os

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.conf import settings

import yt_dlp
import assemblyai as aai
from google import genai
from .models import BlogPost
from dotenv import load_dotenv

# ================= ENV =================
load_dotenv()

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)
aai.settings.api_key = ASSEMBLYAI_API_KEY


# ================= PAGE =================
@login_required
def index(request):
    return render(request, "index.html")


# ================= API =================
@csrf_exempt
def generate_blog(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        body = json.loads(request.body)
        url = body.get("link")

        if not url:
            return JsonResponse({"error": "YouTube link required"}, status=400)

        #get youtube_title
        title = get_youtube_title(url)
        audio_path = download_audio(url)

        if not title or not audio_path:
            return JsonResponse({"error": "Failed to process YouTube video"}, status=500)

        #get transcript
        transcript = transcribe_audio(audio_path)
        if not transcript:
            return JsonResponse({"error": "Transcription failed"}, status=500)

        #use Gemini to generate the blog
        blog = generate_blog_text(transcript, title)
        if not blog:
            return JsonResponse({"error": "Blog generation failed"}, status=500)

        # save blog article to database
        new_blog_article = BlogPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=url,
            generated_content=blog,
        )
        new_blog_article.save()

        # return blog article as a response
        return JsonResponse({"content": blog})

    except Exception as e:
        print("SERVER ERROR:", e)
        return JsonResponse({"error": "Internal server error"}, status=500)


# ================= YOUTUBE =================
def get_youtube_title(url):
    try:
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("title")
    except Exception as e:
        print("TITLE ERROR:", e)
        return None


def download_audio(url):
    try:
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

        ydl_opts = {
            "format": "bestaudio",
            "outtmpl": os.path.join(settings.MEDIA_ROOT, "%(id)s.%(ext)s"),
            "quiet": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)

    except Exception as e:
        print("DOWNLOAD ERROR:", e)
        return None


# ================= TRANSCRIBE =================
def transcribe_audio(path):
    try:
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(path)
        return transcript.text
    except Exception as e:
        print("TRANSCRIBE ERROR:", e)
        return None


# ================= GEMINI =================
def generate_blog_text(transcript, title):
    try:
        prompt = f"""
                Based on the following transcript from a YouTube video, write a comprehensive blog article, write it based on the transcript, but dont make it look like a youtube video, make it look like a proper blog article

                Title: {title}

                Rules:
                - Do NOT mention YouTube or video
                - Use headings and paragraphs
                - Clear explanation
                - Formal blog style

                Transcript:
                {transcript}
                """

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
        )

        return response.text

    except Exception as e:
        print("GEMINI ERROR:", e)
        return None

# ================= BLOG =================
def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')


# ================= AUTH =================
def user_login(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password"),
        )
        if user:
            login(request, user)
            return redirect("/")
        return render(request, "login.html", {"error": "Invalid credentials"})

    return render(request, "login.html")


def user_signup(request):
    if request.method == "POST":
        User.objects.create_user(
            username=request.POST.get("username"),
            password=request.POST.get("password"),
        )
        return redirect("/login/")

    return render(request, "signup.html")


def user_logout(request):
    logout(request)
    return redirect("/login")
