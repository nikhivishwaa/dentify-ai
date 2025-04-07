from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from .models import User
import datetime as dt
import random as rd
from django.views.decorators.csrf import csrf_exempt
from rest_framework.parsers import JSONParser
import io
from .forms import ProfileEditForm
from django.db.models import Q


User = get_user_model()

from accounts.helpers.validations import SignupDataValidation, ProfileUpdateDataValidation, PasswordUpdateDataValidation
from accounts.helpers.utils import otp_helper, forgot_otp_helper
import json


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        dataval = SignupDataValidation(request.POST)
        if dataval.is_valid():  
            d = dataval.data   
            print(d)       
            user = User.objects.filter(Q(email = d['email'].lower()) | Q(phone = d['phone']))
            if user.exists():
                messages.error(request, "User already exist")
                return redirect('login')

            else:
                user = User.objects.create_user(**dataval.data)
                user.set_password(dataval.password)
                user.save()
                print('registered successfully', user)
                # otp_helper(user)
                messages.success(request, "Account Created")
                # messages.success(request, "We have sent an OTP to your email for verification")
        
                # renering verify email page on signup route
                # return render(request, 'accounts/verifyemail.html', context={'email':user.email, "status":"sent"})
                return redirect('login')
        else:
            print(dataval.errors, dataval.data)
            messages.error(request, dataval.errors)
            return render(request, 'accounts/signup.html', context = dataval.data)

    return render(request, 'accounts/signup.html') 

@login_required(login_url="login")
def verification_otp(request):
    if request.user.verified:
        return redirect('dashboard')
    else:
        otp_helper(request.user)
        messages.success(request, "OTP has been sent to your email for verification")
        return redirect('verifyemail')
    


def verifyemail(request):    
    if request.method == 'POST':
        email = request.POST.get('email', '').lower()
        otp = request.POST.get('otp', '')
        resend = request.POST.get('resend', '')

        remaining = 0
        user = None

        # first get the user
        if request.user.is_authenticated:
            user = request.user
        elif email:
            user = User.objects.filter(email = email).first()
        else:
            messages.error(request, f"{'OTP' if not otp else 'Email'} is missing")
            messages.warning(request, "Login to Continue Verification Process")
            return redirect('login')
        
        #  now process with the user
        if user is not None:
            if user.verified:
                messages.warning(request, "Already verified")
                return redirect('login')
            
            # calculate how many seconds left for otp to be valid
            if user.email_otp_ts is not None:
                remaining = 600 - (dt.datetime.now(dt.timezone.utc) - user.email_otp_ts).seconds
                remaining = max(remaining, 0)

            # if user requested to resend otp
            if resend == 'resend':
                if remaining and user.email_otp:
                    messages.warning(request, f"Wait {round(remaining/60)} more minutes {remaining%60} seconds for new OTP")
                else:
                    otp_helper(user)
                    messages.info(request, "OTP has been resent successfully")
                    return render(request, 'accounts/verifyemail.html', context={'email':user.email, 'status': 'rensend'})
            
            # if otp is expired
            elif not remaining:
                user.email_otp = ''
                user.save()
                messages.error(request, "OTP Expired")
                return render(request, 'accounts/verifyemail.html', context={'email':email, 'status': 'expired'})

            # if otp is valid
            elif user.email_otp == otp:
                user.verified = True
                user.email_otp = ''
                user.email_verified_at = dt.datetime.now(dt.timezone.utc)
                user.email_otp_ts = None
                user.save()
                messages.success(request, "Email Verified")
                return redirect('login')
            
            # if otp is invalid
            else:
                messages.error(request, "Invalid OTP")
                return render(request, 'accounts/verifyemail.html', context={'email':email, 'status':'invalid'})

    
    # handle GET request
    if request.user.is_authenticated:
        if request.user.verified:
            return redirect('dashboard')
       
        else:
            return render(request, 'accounts/verifyemail.html', context={'email':request.user.email, 'status':'fresh'})
    return redirect('login')


def logoutuser(request):
    logout(request)
    return redirect('/')

@login_required(login_url="login")
@csrf_exempt
def profile_api(request):
    response = {'success': True}
    if request.method == 'POST':
        stream = io.BytesIO(request.body)               
        data = JSONParser().parse(stream)
        profile = ProfileUpdateDataValidation(data)
        if profile.is_valid():  
            d = profile.data          
            user = request.user
            print(dir(user))
            for key, value in d.items():
                user.__setattr__(key,value)

            user.save()
            print('updated successfully', user)
        
            response = {
                'success':True,
                'message': "Profile Updated Successfully",
                'data':{
                    'email' : user.email,
                    'first_name' : user.first_name,
                    'last_name' : user.last_name,
                    'verified' : user.verified,
                    'phone' : user.phone,
                    'profile_pic': user.profile_pic.url if user.profile_pic else ''
                }
        }
        else:
            response['success'] = False
            response['message'] = profile.errors
    else:
        response['data'] = {
            'email' : request.user.email,
            'first_name' : request.user.first_name,
            'last_name' : request.user.last_name,
            'verified' : request.user.verified,
            'phone' : request.user.phone,
            'profile_pic': request.user.profile_pic.url if request.user.profile_pic else ''
        }

    return HttpResponse(json.dumps(response), content_type='application/json')

@login_required(login_url="login")  
def profileform(request):
    if request.method == 'POST':
        u = request.user
        print(request.FILES)
        u.profile_pic = request.FILES.get('profile_pic', '')
        u.gender = request.POST.get('gender','')
        u.dob = request.POST.get('dob','')
        u.save()
        messages.success(request, "Profile Updated Successfully")
        return redirect('dashboard')
    return render(request, 'accounts/profileform.html')

def userauth(request):
    if request.user.is_authenticated:
        # return redirect('send_otp')
        return redirect('dashboard')
        

    elif request.method == 'POST':
        email = request.POST.get('email', '').lower()
        password = request.POST.get('password', '')
        if email and password:
            user = authenticate(email=email, password=password)
            print('user', user, 'logged in')
            if user is not None:
                login(request, user)
                # return redirect('send_otp')             
                return redirect('dashboard')

            else:
                messages.error(request, "Invalid Credentials")
                return redirect('login')
        else:
            messages.error(request, f"{'Password' if not password else 'Email'} is missing")
            return render(request, 'accounts/login.html')


    return render(request, 'accounts/login.html')

def forgotpasswordotp(request):        
    if request.method == 'POST':
        email = request.POST.get('email', '').lower()
        otp = request.POST.get('otp', '')
        resend = request.POST.get('resend', '')

        if email:
            user = User.objects.filter(email = email).first()
            if user is not None:
                remaining = 0
                # calculate how many seconds left for otp to be valid
                if user.fget_otp_ts is not None:
                    remaining = 600 - (dt.datetime.now(dt.timezone.utc) - user.fget_otp_ts).seconds
                    remaining = max(remaining, 0)

                # if user requested to resend otp
                if resend == 'resend':
                    if remaining and user.fget_otp:
                        messages.warning(request, f"Wait {round(remaining/60)} more minutes {remaining%60} seconds for new OTP")
                    else:
                        forgot_otp_helper(user)
                        messages.info(request, f"OTP has been {'resent' if user.fget_otp else 'sent'} successfully")
                    return render(request, 'accounts/forgotpassword.html', context={'email':user.email})
                
                # if otp is expired
                elif not remaining:
                    user.fget_otp = ''
                    user.save()
                    messages.error(request, "OTP Expired")
                    return render(request, 'accounts/forgotpassword.html', context={'email':email, 'status':'expired'})

                # if otp is valid
                elif user.fget_otp == otp:
                    p_token = f'${user.id}_TS_{dt.datetime.now().timestamp()/rd.randint(111, 5964)}${hex(int(user.phone))}' 
                    user.fget_token = p_token
                    user.fget_otp = ''
                    user.save()
                    messages.success(request, "OTP Verified. Now create new password")

                    response = redirect('newpassword')
                    response.set_cookie('p_token', user.fget_token, max_age=600)
                    return response
                
                # if otp is invalid
                else:
                    messages.error(request, "Invalid OTP")
                    return render(request, 'accounts/forgotpassword.html', context={'email':email, 'status':'invalid'})
            else:
                messages.error(request, "Invalid User Email")
                return redirect('forgotpassword')
        else:
            messages.error(request, f"{'OTP' if not otp else 'Email'} is missing")
            return redirect('forgotpassword')

    return render(request, 'accounts/forgotpassword.html', context={'status': 'resend'})

def newpassword(request):
    p_token = request.COOKIES.get('p_token', None)
    print(request.COOKIES)
    print(p_token)
    if p_token is not None:
        if request.method == 'POST':
            dataval = PasswordUpdateDataValidation(request.POST)
            if dataval.is_valid():  
                d = dataval.data          
                user = User.objects.filter(fget_token = p_token).first()
                if user is not None:
                    user.set_password(dataval.password)
                    user.fget_token = ''
                    user.last_fget = dt.datetime.now(dt.timezone.utc)
                    user.save()
                    messages.success(request, "Password Changed Successfully")

                    response = redirect('login')
                    response.set_cookie('p_token', '', max_age=0)
                    return response

                else:
                    messages.error(request, "User not exist")           
                    return render(request, 'accounts/newpassword.html')
            else:
                messages.error(request, dataval.errors)
                return render(request, 'accounts/newpassword.html')

        else:
            return render(request, 'accounts/newpassword.html')

    else:   
        messages.warning(request, "Maximum Time Exceeded. Try again.")
        return redirect('forgotpassword')
    
#User Updation code

@login_required
def profile(request):
    user = request.user

    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.phone = form.cleaned_data['phone']
            user.gender = form.cleaned_data['gender']
            user.dob = form.cleaned_data['dob']
            user.bio = form.cleaned_data.get('bio', '')  # Make sure to handle bio if needed
            if 'profile_pic' in request.FILES:
                user.profile_pic = request.FILES['profile_pic']

            user.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ProfileEditForm(instance=user)

    return render(request, 'home/profile.html', {'form': form})
