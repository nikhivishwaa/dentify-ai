from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from home.models import Prediction, ContactMessage
from django.core.mail import send_mail
from django.contrib import messages
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.files.base import ContentFile
from django.views.decorators.csrf import csrf_exempt
import asyncio
from worker.handle_xray import make_prediction
import datetime as dt

@login_required
def home(request):
    # check user verified status
    if request.user.verified:
        return HttpResponse("Welcome to the Dentify AI platform!")
    
    return redirect('login')

def landingpage(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'home/landingpage.html')

@login_required(login_url='login')
def dashboard(request):
    history = Prediction.objects.filter(user=request.user)[:10]
    return render(request, 'home/dashboard.html', context={'history':history})

@login_required(login_url='login')
@csrf_exempt
def predict(request):
    if request.method == 'POST':
        file = request.FILES.get('xray_file')
        print(file)
        if file:
            try:
                result = asyncio.run(make_prediction(file))
                # result = make_prediction(file)
                print(dt.datetime.now(), result)

                res = {
                    "message": "Prediction successful",
                    "result":result,
                    # "image": file
                }
                print('sent')
                return JsonResponse(res)
            except Exception as e:
                print(e)
                res = {
                    "message": "Prediction failed",
                    "error":str(e)
                }
                return JsonResponse(res, status=400)
    return JsonResponse({"message": "Prediction failed"}, status=400)

@login_required(login_url='login')
def profile(request):
    return render(request, 'home/profile.html')


# view for handling contact form
def contact_view(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        subject = request.POST.get("subject")
        message = request.POST.get("message")

        # Validate the form data
        if not name or not email or not subject or not message:
            messages.error(request, "All fields are required.")
            return redirect("landingpage")  # Replace with your landing page view name

        # Save the data to the database
        contact_message = ContactMessage(
            name=name, email=email, subject=subject, message=message
        )
        contact_message.save()

        # html_message = render_to_string(
        #     "home/contact_email.html",
        #     {
        #         "name": name,
        #         "subject": subject,
        #         "message": message,
        #         "from_email": settings.EMAIL_HOST_USER,
        #     },
        # )
        # plain_message = strip_tags(html_message)

        # # Send an email notification to the client
        # send_mail(
        #     subject=f"Confirmation: {subject}",
        #     message=plain_message,
        #     from_email=settings.EMAIL_HOST_USER,  # Replace with your email
        #     recipient_list=[email],
        #     fail_silently=False,
        #     html_message=html_message,
        # )

        # # Send a notification to yourself (optional)
        # send_mail(
        #     subject=f"New Contact Form Submission: {subject}",
        #     message=f"New message from {name} ({email}):\n\n{message}",
        #     from_email=settings.EMAIL_HOST_USER,  # Replace with your email
        #     recipient_list=[settings.EMAIL_HOST_USER],  # Replace with your email
        #     fail_silently=False,
        # )

        # Show a success message
        messages.success(
            request, "Thank you for your message. We will get back to you shortly."
        )
        return redirect("landingpage")  # Replace with your landing page view name

    return render(request, "home/landing.html")  # Replace with your template

# terms of service view
def terms_of_service(request):
    return render(request, 'home/components/terms_of_service.html')

# privacy policy view
def privacy_policy(request):
    return render(request, 'home/components/privacy_policy.html')

# cookie policy view
def cookie_policy(request):
    return render(request, 'home/components/cookie_policy.html')

