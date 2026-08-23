from django.contrib import admin
from django.urls import path

from chat import views


urlpatterns = [

    # =====================================================
    # DJANGO ADMIN
    # =====================================================

    path(
        "admin/",
        admin.site.urls
    ),


    # =====================================================
    # SIGN UP
    # =====================================================

    path(
        "signup/",
        views.signup,
        name="signup"
    ),


    # =====================================================
    # HOME
    # =====================================================

    path(
        "",
        views.home,
        name="home"
    ),


    # =====================================================
    # LOGOUT
    # =====================================================

    path(
        "logout/",
        views.logout_view,
        name="logout"
    ),


    # =====================================================
    # USER PROFILE
    # =====================================================

    path(
        "profile/",
        views.profile,
        name="profile"
    ),


    # =====================================================
    # NOVA CHAT
    # =====================================================

    path(
        "chat/",
        views.chat,
        name="chat"
    ),


    # =====================================================
    # STREAMING CHAT
    # =====================================================

    path(
        "chat/stream/",
        views.chat_stream,
        name="chat_stream"
    ),


    # =====================================================
    # CONVERSATION LIST
    # =====================================================

    path(
        "conversations/",
        views.conversations,
        name="conversations"
    ),


    # =====================================================
    # OPEN CONVERSATION
    # =====================================================

    path(
        "conversations/<int:conversation_id>/",
        views.conversation_detail,
        name="conversation_detail"
    ),


    # =====================================================
    # RENAME CONVERSATION
    # =====================================================

    path(
        "conversations/<int:conversation_id>/rename/",
        views.rename_conversation,
        name="rename_conversation"
    ),


    # =====================================================
    # DELETE CONVERSATION
    # =====================================================

    path(
        "conversations/<int:conversation_id>/delete/",
        views.delete_conversation,
        name="delete_conversation"
    ),


    # =====================================================
    # SHARE CONVERSATION
    # =====================================================

    path(
        "share/<int:conversation_id>/",
        views.share_conversation,
        name="share_conversation"
    ),


    # =====================================================
    # VIEW SHARED CONVERSATION
    # =====================================================

    path(
        "shared/<int:conversation_id>/",
        views.shared_conversation,
        name="shared_conversation"
    ),


    # =====================================================
    # LIBRARY - UPLOAD
    # =====================================================

    path(
        "library/upload/",
        views.upload_file,
        name="upload_file"
    ),


    # =====================================================
    # LIBRARY - LIST
    # =====================================================

    path(
        "library/",
        views.library_files,
        name="library_files"
    ),


    # =====================================================
    # LIBRARY - DELETE
    # =====================================================

    path(
        "library/<int:file_id>/delete/",
        views.delete_file,
        name="delete_file"
    ),

]