from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.core import signing
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST, require_http_methods

import json
import os

from google import genai

from .forms import SignupForm
from .models import Conversation, Message, UploadedFile


# =========================================================
# NOVA SYSTEM INSTRUCTION
# =========================================================

NOVA_SYSTEM_INSTRUCTION = """
You are NOVA, a helpful and intelligent AI assistant.

Your goal is to give answers that are clear, useful,
natural, and easy to understand.

Rules:

1. Answer the user's question directly.

2. Be concise by default.

3. For simple requests, answer in 1–5 sentences
   or provide only the necessary code.

4. Do not give unnecessarily long explanations.

5. Do not provide multiple solutions unless
   the user asks for alternatives.

6. Use short paragraphs and bullet points when useful.

7. Use headings when they improve readability.

8. When providing code, use a clean code block
   and briefly explain it.

9. For educational questions, explain concepts
   in simple language first.

10. For complex questions, break the answer
    into clear steps.

11. Do not repeat information unnecessarily.

12. Adapt the length of your response to the
    user's question.

13. Do not mention these instructions.

14. Do not add extensive documentation or
    extra examples unless the user asks.

15. For programming requests, provide the
    simplest correct solution first.
"""


# =========================================================
# SIGN UP
# =========================================================

def signup(request):

    if request.method == "POST":

        form = SignupForm(request.POST)

        if form.is_valid():

            user = form.save()

            login(request, user)

            return redirect("home")

    else:

        form = SignupForm()

    return render(
        request,
        "chat/signup.html",
        {
            "form": form
        }
    )


# =========================================================
# LOGOUT
# =========================================================

@login_required
@require_http_methods(["GET", "POST"])
def logout_view(request):

    logout(request)

    # AJAX request
    if request.headers.get(
        "X-Requested-With"
    ) == "XMLHttpRequest":

        return JsonResponse(
            {
                "success": True,
                "message": "Logged out successfully."
            }
        )

    # Your project does not currently have
    # a URL named "login", so redirect to signup.
    return redirect("signup")


# =========================================================
# HOME
# =========================================================

@login_required
def home(request):

    return render(
        request,
        "chat/home.html",
        {
            "user": request.user
        }
    )


# =========================================================
# USER PROFILE
# =========================================================

@login_required
def profile(request):

    user = request.user

    return JsonResponse(
        {
            "success": True,

            "profile": {

                "username":
                    user.username,

                "email":
                    user.email,

                "first_name":
                    user.first_name,

                "last_name":
                    user.last_name,

                "date_joined":
                    user.date_joined.strftime(
                        "%d %b %Y"
                    ),
            }
        }
    )


# =========================================================
# CONVERSATION LIST
# =========================================================

@login_required
def conversations(request):

    user_conversations = (
        Conversation.objects
        .filter(
            user=request.user
        )
        .order_by("-updated_at")
    )

    conversation_list = []

    for conversation in user_conversations:

        conversation_list.append(
            {
                "id":
                    conversation.id,

                "title":
                    conversation.title,

                "updated_at":
                    conversation.updated_at.strftime(
                        "%d %b %Y, %I:%M %p"
                    ),
            }
        )

    return JsonResponse(
        {
            "success": True,

            "conversations":
                conversation_list
        }
    )


# =========================================================
# OPEN CONVERSATION
# =========================================================

@login_required
def conversation_detail(
    request,
    conversation_id
):

    try:

        conversation = (
            Conversation.objects.get(
                id=conversation_id,
                user=request.user
            )
        )

    except Conversation.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "error":
                    "Conversation not found."
            },
            status=404
        )

    messages = (
        conversation.messages
        .order_by("created_at")
    )

    message_list = []

    for message in messages:

        message_list.append(
            {
                "role":
                    message.role,

                "content":
                    message.content,

                "created_at":
                    message.created_at.strftime(
                        "%d %b %Y, %I:%M %p"
                    ),
            }
        )

    return JsonResponse(
        {
            "success": True,

            "conversation": {

                "id":
                    conversation.id,

                "title":
                    conversation.title,
            },

            "messages":
                message_list
        }
    )


# =========================================================
# GENERATE CONVERSATION TITLE
# =========================================================

def generate_conversation_title(
    user_message
):

    title = user_message.strip()

    if not title:

        return "New Conversation"

    title = " ".join(
        title.split()
    )

    prefixes = [
        "please",
        "can you",
        "could you",
        "would you",
        "help me",
        "i want to",
        "i need to",
        "tell me",
    ]

    lower_title = title.lower()

    for prefix in prefixes:

        if lower_title.startswith(prefix):

            title = title[
                len(prefix):
            ].strip()

            break

    if title:

        title = (
            title[0].upper()
            + title[1:]
        )

    if len(title) > 50:

        title = (
            title[:50]
            .rstrip()
        )

        if " " in title:

            title = (
                title.rsplit(
                    " ",
                    1
                )[0]
            )

        title += "..."

    return title


# =========================================================
# BUILD GEMINI HISTORY
# =========================================================

def build_conversation_history(
    conversation
):

    previous_messages = (
        conversation.messages
        .order_by("created_at")
    )

    conversation_history = []

    for message in previous_messages:

        if message.role == "user":

            conversation_history.append(
                {
                    "role":
                        "user",

                    "parts": [
                        {
                            "text":
                                message.content
                        }
                    ]
                }
            )

        elif message.role == "assistant":

            conversation_history.append(
                {
                    "role":
                        "model",

                    "parts": [
                        {
                            "text":
                                message.content
                        }
                    ]
                }
            )

    return conversation_history


# =========================================================
# NORMAL CHAT
# =========================================================

@login_required
@require_POST
def chat(request):

    try:

        data = json.loads(
            request.body.decode(
                "utf-8"
            )
        )

        user_message = (
            data.get(
                "message",
                ""
            )
            .strip()
        )

        conversation_id = data.get(
            "conversation_id"
        )

        # -------------------------------------------------
        # Validate
        # -------------------------------------------------

        if not user_message:

            return JsonResponse(
                {
                    "success": False,

                    "response":
                        "Please type a message first."
                },
                status=400
            )

        # -------------------------------------------------
        # API KEY
        # -------------------------------------------------

        api_key = os.environ.get(
            "GEMINI_API_KEY"
        )

        if not api_key:

            print(
                "ERROR: GEMINI_API_KEY is not set."
            )

            return JsonResponse(
                {
                    "success": False,

                    "response":
                        "Gemini API key is not configured."
                },
                status=500
            )

        # -------------------------------------------------
        # Find conversation
        # -------------------------------------------------

        conversation = None

        if conversation_id:

            try:

                conversation = (
                    Conversation.objects.get(
                        id=conversation_id,
                        user=request.user
                    )
                )

            except Conversation.DoesNotExist:

                conversation = None

        # -------------------------------------------------
        # Create conversation
        # -------------------------------------------------

        if conversation is None:

            conversation = (
                Conversation.objects.create(
                    user=request.user,

                    title=
                        generate_conversation_title(
                            user_message
                        )
                )
            )

        # -------------------------------------------------
        # Save user message
        # -------------------------------------------------

        Message.objects.create(
            conversation=
                conversation,

            role="user",

            content=
                user_message
        )

        # -------------------------------------------------
        # Build history
        # -------------------------------------------------

        conversation_history = (
            build_conversation_history(
                conversation
            )
        )

        # -------------------------------------------------
        # Gemini
        # -------------------------------------------------

        client = genai.Client(
            api_key=api_key
        )

        response = (
            client.models.generate_content(

                model=
                    "gemini-2.5-flash",

                contents=
                    conversation_history,

                config={
                    "system_instruction":
                        NOVA_SYSTEM_INSTRUCTION
                }
            )
        )

        ai_response = (
            getattr(
                response,
                "text",
                None
            )
        )

        if not ai_response:

            ai_response = (
                "Sorry, I couldn't generate a response."
            )

        # -------------------------------------------------
        # Save assistant message
        # -------------------------------------------------

        Message.objects.create(
            conversation=
                conversation,

            role="assistant",

            content=
                ai_response
        )

        # -------------------------------------------------
        # Return
        # -------------------------------------------------

        return JsonResponse(
            {
                "success": True,

                "response":
                    ai_response,

                "conversation_id":
                    conversation.id,

                "conversation_title":
                    conversation.title
            }
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,

                "response":
                    "Invalid request format."
            },
            status=400
        )

    except Exception as e:

        print(
            "\n========== NOVA ERROR =========="
        )

        print(e)

        print(
            "================================\n"
        )

        return JsonResponse(
            {
                "success": False,

                "response":
                    "Sorry, NOVA could not get a response."
            },
            status=500
        )


# =========================================================
# STREAMING CHAT
# =========================================================

@login_required
@require_POST
def chat_stream(request):

    try:

        data = json.loads(
            request.body.decode(
                "utf-8"
            )
        )

        user_message = (
            data.get(
                "message",
                ""
            )
            .strip()
        )

        conversation_id = data.get(
            "conversation_id"
        )

        if not user_message:

            return JsonResponse(
                {
                    "success": False,

                    "error":
                        "Please type a message first."
                },
                status=400
            )

        # -------------------------------------------------
        # API KEY
        # -------------------------------------------------

        api_key = os.environ.get(
            "GEMINI_API_KEY"
        )

        if not api_key:

            return JsonResponse(
                {
                    "success": False,

                    "error":
                        "Gemini API key is not configured."
                },
                status=500
            )

        # -------------------------------------------------
        # Find conversation
        # -------------------------------------------------

        conversation = None

        if conversation_id:

            try:

                conversation = (
                    Conversation.objects.get(
                        id=conversation_id,
                        user=request.user
                    )
                )

            except Conversation.DoesNotExist:

                conversation = None

        # -------------------------------------------------
        # Create conversation
        # -------------------------------------------------

        if conversation is None:

            conversation = (
                Conversation.objects.create(

                    user=request.user,

                    title=
                        generate_conversation_title(
                            user_message
                        )
                )
            )

        # -------------------------------------------------
        # Save user message
        # -------------------------------------------------

        Message.objects.create(
            conversation=
                conversation,

            role="user",

            content=
                user_message
        )

        # -------------------------------------------------
        # History
        # -------------------------------------------------

        conversation_history = (
            build_conversation_history(
                conversation
            )
        )

        # -------------------------------------------------
        # Gemini client
        # -------------------------------------------------

        client = genai.Client(
            api_key=api_key
        )

        # -------------------------------------------------
        # Generator
        # -------------------------------------------------

        def generate():

            full_response = ""

            try:

                response_stream = (
                    client.models
                    .generate_content_stream(

                        model=
                            "gemini-2.5-flash",

                        contents=
                            conversation_history,

                        config={
                            "system_instruction":
                                NOVA_SYSTEM_INSTRUCTION
                        }
                    )
                )

                for chunk in response_stream:

                    text = getattr(
                        chunk,
                        "text",
                        None
                    )

                    if text:

                        full_response += text

                        yield (
                            json.dumps(
                                {
                                    "type":
                                        "chunk",

                                    "text":
                                        text,

                                    "conversation_id":
                                        conversation.id,

                                    "conversation_title":
                                        conversation.title
                                }
                            )
                            + "\n"
                        )

                # -------------------------------------------------
                # Save complete response
                # -------------------------------------------------

                if full_response:

                    Message.objects.create(

                        conversation=
                            conversation,

                        role="assistant",

                        content=
                            full_response
                    )

                # -------------------------------------------------
                # Done
                # -------------------------------------------------

                yield (
                    json.dumps(
                        {
                            "type":
                                "done",

                            "conversation_id":
                                conversation.id,

                            "conversation_title":
                                conversation.title
                        }
                    )
                    + "\n"
                )

            except Exception as e:

                print(
                    "STREAMING ERROR:",
                    e
                )

                yield (
                    json.dumps(
                        {
                            "type":
                                "error",

                            "message":
                                "NOVA could not generate a response."
                        }
                    )
                    + "\n"
                )

        response = StreamingHttpResponse(
            generate(),
            content_type=
                "application/x-ndjson"
        )

        response["Cache-Control"] = (
            "no-cache"
        )

        response["X-Accel-Buffering"] = (
            "no"
        )

        return response

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,

                "error":
                    "Invalid request format."
            },
            status=400
        )

    except Exception as e:

        print(
            "\n====== STREAM ERROR ======"
        )

        print(e)

        print(
            "==========================\n"
        )

        return JsonResponse(
            {
                "success": False,

                "error":
                    "Streaming request failed."
            },
            status=500
        )


# =========================================================
# DELETE CONVERSATION
# =========================================================

@login_required
@require_POST
def delete_conversation(
    request,
    conversation_id
):

    try:

        conversation = (
            Conversation.objects.get(
                id=conversation_id,
                user=request.user
            )
        )

        conversation.delete()

        return JsonResponse(
            {
                "success": True,

                "message":
                    "Conversation deleted successfully."
            }
        )

    except Conversation.DoesNotExist:

        return JsonResponse(
            {
                "success": False,

                "message":
                    "Conversation not found."
            },
            status=404
        )

    except Exception as e:

        print(
            "\n====== DELETE CONVERSATION ERROR ======"
        )

        print(e)

        print(
            "========================================\n"
        )

        return JsonResponse(
            {
                "success": False,

                "message":
                    "Sorry, the conversation could not be deleted."
            },
            status=500
        )


# =========================================================
# RENAME CONVERSATION
# =========================================================

@login_required
@require_POST
def rename_conversation(
    request,
    conversation_id
):

    try:

        conversation = (
            Conversation.objects.get(
                id=conversation_id,
                user=request.user
            )
        )

        data = json.loads(
            request.body.decode(
                "utf-8"
            )
        )

        new_title = (
            data.get(
                "title",
                ""
            )
            .strip()
        )

        if not new_title:

            return JsonResponse(
                {
                    "success": False,

                    "message":
                        "Title cannot be empty."
                },
                status=400
            )

        conversation.title = (
            new_title[:200]
        )

        conversation.save(
            update_fields=[
                "title",
                "updated_at"
            ]
        )

        return JsonResponse(
            {
                "success": True,

                "title":
                    conversation.title
            }
        )

    except Conversation.DoesNotExist:

        return JsonResponse(
            {
                "success": False,

                "message":
                    "Conversation not found."
            },
            status=404
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,

                "message":
                    "Invalid request."
            },
            status=400
        )

    except Exception as e:

        print(
            "\n====== RENAME ERROR ======"
        )

        print(e)

        print(
            "==========================\n"
        )

        return JsonResponse(
            {
                "success": False,

                "message":
                    "Could not rename conversation."
            },
            status=500
        )


# =========================================================
# LIBRARY - UPLOAD FILE
# =========================================================

@login_required
@require_POST
def upload_file(request):

    uploaded_file = request.FILES.get(
        "file"
    )

    # -----------------------------------------------------
    # Check file
    # -----------------------------------------------------

    if not uploaded_file:

        return JsonResponse(
            {
                "success": False,

                "message":
                    "No file was selected."
            },
            status=400
        )

    # -----------------------------------------------------
    # Optional conversation
    # -----------------------------------------------------

    conversation_id = request.POST.get(
        "conversation_id"
    )

    conversation = None

    if conversation_id:

        try:

            conversation = (
                Conversation.objects.get(
                    id=conversation_id,
                    user=request.user
                )
            )

        except Conversation.DoesNotExist:

            return JsonResponse(
                {
                    "success": False,

                    "message":
                        "Conversation not found."
                },
                status=404
            )

    # -----------------------------------------------------
    # Allowed extensions
    # -----------------------------------------------------

    allowed_extensions = [

        ".pdf",
        ".doc",
        ".docx",
        ".txt",

        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",

    ]

    file_name = (
        uploaded_file.name.lower()
    )

    file_extension = ""

    if "." in file_name:

        file_extension = (
            "."
            + file_name.rsplit(
                ".",
                1
            )[1]
        )

    # -----------------------------------------------------
    # Validate extension
    # -----------------------------------------------------

    if file_extension not in allowed_extensions:

        return JsonResponse(
            {
                "success": False,

                "message":
                    "This file type is not supported."
            },
            status=400
        )

    # -----------------------------------------------------
    # Maximum size: 10 MB
    # -----------------------------------------------------

    max_file_size = (
        10 * 1024 * 1024
    )

    if uploaded_file.size > max_file_size:

        return JsonResponse(
            {
                "success": False,

                "message":
                    "File is too large. Maximum size is 10 MB."
            },
            status=400
        )

    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    try:

        library_file = (
            UploadedFile.objects.create(

                user=request.user,

                conversation=
                    conversation,

                file=
                    uploaded_file,

                original_name=
                    uploaded_file.name,

                file_type=
                    uploaded_file.content_type
                    or "",

                file_size=
                    uploaded_file.size
            )
        )

        return JsonResponse(
            {
                "success": True,

                "message":
                    "File uploaded successfully.",

                "file": {

                    "id":
                        library_file.id,

                    "name":
                        library_file.original_name,

                    "type":
                        library_file.file_type,

                    "size":
                        library_file.file_size,

                    "uploaded_at":
                        library_file.uploaded_at.strftime(
                            "%d %b %Y, %I:%M %p"
                        ),

                    "url":
                        library_file.file.url,
                }
            },
            status=201
        )

    except Exception as e:

        print(
            "\n========== FILE UPLOAD ERROR =========="
        )

        print(e)

        print(
            "========================================\n"
        )

        return JsonResponse(
            {
                "success": False,

                "message":
                    "Sorry, the file could not be uploaded."
            },
            status=500
        )


# =========================================================
# LIBRARY - LIST FILES
# =========================================================

@login_required
def library_files(request):

    files = (
        UploadedFile.objects
        .filter(
            user=request.user
        )
        .order_by("-uploaded_at")
    )

    file_list = []

    for uploaded_file in files:

        try:

            file_url = (
                uploaded_file.file.url
            )

        except ValueError:

            file_url = ""

        file_list.append(
            {
                "id":
                    uploaded_file.id,

                "name":
                    uploaded_file.original_name,

                "type":
                    uploaded_file.file_type,

                "size":
                    uploaded_file.file_size,

                "uploaded_at":
                    uploaded_file.uploaded_at.strftime(
                        "%d %b %Y, %I:%M %p"
                    ),

                "url":
                    file_url,

                "conversation_id":
                    (
                        uploaded_file.conversation.id
                        if uploaded_file.conversation
                        else None
                    ),
            }
        )

    return JsonResponse(
        {
            "success": True,

            "files":
                file_list
        }
    )


# =========================================================
# LIBRARY - DELETE FILE
# =========================================================

@login_required
@require_POST
def delete_file(
    request,
    file_id
):

    try:

        uploaded_file = (
            UploadedFile.objects.get(
                id=file_id,
                user=request.user
            )
        )

        # Delete physical file
        if uploaded_file.file:

            try:

                uploaded_file.file.delete(
                    save=False
                )

            except Exception as file_error:

                print(
                    "Physical file delete error:",
                    file_error
                )

        # Delete database record
        uploaded_file.delete()

        return JsonResponse(
            {
                "success": True,

                "message":
                    "File deleted successfully."
            }
        )

    except UploadedFile.DoesNotExist:

        return JsonResponse(
            {
                "success": False,

                "message":
                    "File not found."
            },
            status=404
        )

    except Exception as e:

        print(
            "\n========== FILE DELETE ERROR =========="
        )

        print(e)

        print(
            "=======================================\n"
        )

        return JsonResponse(
            {
                "success": False,

                "message":
                    "Sorry, the file could not be deleted."
            },
            status=500
        )


# =========================================================
# CREATE SHARE LINK
# =========================================================

@login_required
@require_POST
def share_conversation(
    request,
    conversation_id
):

    try:

        conversation = (
            Conversation.objects.get(
                id=conversation_id,
                user=request.user
            )
        )

    except Conversation.DoesNotExist:

        return JsonResponse(
            {
                "success": False,

                "message":
                    "Conversation not found."
            },
            status=404
        )

    # -----------------------------------------------------
    # Create signed token
    # -----------------------------------------------------

    token = signing.dumps(
        {
            "conversation_id":
                conversation.id
        },

        salt=
            "nova-conversation-share"
    )

    # -----------------------------------------------------
    # Public URL
    # -----------------------------------------------------

    public_base_url = os.environ.get(
        "NOVA_PUBLIC_BASE_URL"
    )

    if public_base_url:

        public_base_url = (
            public_base_url
            .rstrip("/")
        )

    else:

        public_base_url = (
            request.build_absolute_uri(
                "/"
            )
            .rstrip("/")
        )

    share_url = (
        f"{public_base_url}"
        f"/share/{token}/"
    )

    return JsonResponse(
        {
            "success": True,

            "share_url":
                share_url,

            "conversation_id":
                conversation.id,

            "conversation_title":
                conversation.title,

            "message":
                "Share link created successfully."
        }
    )


# =========================================================
# OPEN SHARED CONVERSATION
# =========================================================

def shared_conversation(
    request,
    token
):

    try:

        payload = signing.loads(
            token,

            salt=
                "nova-conversation-share",

            max_age=
                60 * 60 * 24 * 30
        )

        conversation_id = (
            payload.get(
                "conversation_id"
            )
        )

        if not conversation_id:

            raise signing.BadSignature()

        conversation = (
            Conversation.objects.get(
                id=conversation_id
            )
        )

    except (
        signing.BadSignature,
        signing.SignatureExpired,
        Conversation.DoesNotExist
    ):

        return render(
            request,

            "chat/shared_chat.html",

            {
                "valid":
                    False,

                "error":
                    "This share link is invalid or has expired."
            },

            status=404
        )

    # -----------------------------------------------------
    # Messages
    # -----------------------------------------------------

    messages = (
        conversation.messages
        .order_by("created_at")
    )

    message_list = []

    for message in messages:

        message_list.append(
            {
                "role":
                    message.role,

                "content":
                    message.content,

                "created_at":
                    message.created_at.strftime(
                        "%d %b %Y, %I:%M %p"
                    )
            }
        )

    return render(
        request,

        "chat/shared_chat.html",

        {
            "valid":
                True,

            "conversation":
                conversation,

            "messages":
                message_list,

            "title":
                conversation.title
        }
    )


# =========================================================
# SHARED CONVERSATION JSON API
# =========================================================

def shared_conversation_api(
    request,
    token
):

    try:

        payload = signing.loads(
            token,

            salt=
                "nova-conversation-share",

            max_age=
                60 * 60 * 24 * 30
        )

        conversation_id = (
            payload.get(
                "conversation_id"
            )
        )

        conversation = (
            Conversation.objects.get(
                id=conversation_id
            )
        )

    except (
        signing.BadSignature,
        signing.SignatureExpired,
        Conversation.DoesNotExist
    ):

        return JsonResponse(
            {
                "success": False,

                "message":
                    "Invalid or expired share link."
            },
            status=404
        )

    messages = (
        conversation.messages
        .order_by("created_at")
    )

    message_list = []

    for message in messages:

        message_list.append(
            {
                "role":
                    message.role,

                "content":
                    message.content,

                "created_at":
                    message.created_at.strftime(
                        "%d %b %Y, %I:%M %p"
                    )
            }
        )

    return JsonResponse(
        {
            "success": True,

            "conversation": {

                "id":
                    conversation.id,

                "title":
                    conversation.title
            },

            "messages":
                message_list
        }
    )