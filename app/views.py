from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db.models import Min, Max, Avg, Count, Q
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
import logging
from django.db import transaction
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os


from .models import Role, UserData, UserProfile, FaceMetadata
from .face_recognition import extract_face_metadata, compare_faces
# Create your views here.

logger = logging.getLogger(__name__)


def login_user(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('login-redirect')
        else:
            messages.error(request, "Invalid username or password")
            return render(request, 'login.html', {})
    else:
        return render(request, 'login.html', {})


@login_required
def login_redirect(request):
    user_profile = request.user.userprofile
    if user_profile.role.name == 'Admin':
        return redirect('admin-dashboard')
    elif user_profile.role.name == 'Enumerator':
        return redirect('enumerator-dashboard')
    else:
        return redirect('login')


@login_required
def admin_view_dashboard(request):
    user_profile = request.user.userprofile
    if user_profile.role.name == 'Admin':
        data = fetch_dashboard_data()
        return render(request, 'admin/dashboard.html', data)
    else:
        # Instead of redirecting to the login page, consider showing a 403 Forbidden page or redirecting to a safe page
        return HttpResponseForbidden("You are not authorized to view this page.")


@login_required
def admin_view_enumerator(request):
    user_profile = request.user.userprofile
    if user_profile.role.name == 'Admin':
        if request.method == 'POST':
            # Extract form data
            first_name = request.POST.get('first_name')
            second_name = request.POST.get('second_name')
            username = request.POST.get('username')
            email = request.POST.get('email')
            phone = request.POST.get('phone')
            id_number = request.POST.get('id_number')
            password = '2024@Password'
            role_id = request.POST.get('role')

            print("Phone:", phone, "ID Number:", id_number)

            logger.warning("creating user")

            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=second_name
                    )
                    # Create UserProfile
                    role = Role.objects.get(id=role_id)
                    logger.warning("User created now creating profile " +
                                   "Phone:"+phone+" ID Number:"+id_number+" Role:"+role.name)

                    UserProfile.objects.update_or_create(
                        user=user,
                        defaults={
                            'phone': phone,
                            'id_number': id_number,
                            'role_id': role_id
                        }
                    )

                messages.success(request, "New Staff created successfully")

            except IntegrityError as e:
                if 'username' in str(e):
                    messages.error(
                        request, "The username has already been taken. Please choose a different one.")
                else:
                    messages.error(
                        request, "An error occurred during staff account creation. Please try again. - {}".format(e))
            except Role.DoesNotExist:
                messages.error(request, "The selected role does not exist.")
            except Exception as e:
                messages.error(
                    request, "An unexpected error occurred: {}".format(e))

            data = fetch_enumerator_data()
            return render(request, 'admin/enumerator.html', data)
        else:
            data = fetch_enumerator_data()
            return render(request, 'admin/enumerator.html', data)
    else:
        # Instead of redirecting to the login page, consider showing a 403 Forbidden page or redirecting to a safe page
        return HttpResponseForbidden("You are not authorized to view this page.")


def fetch_dashboard_data():
    total_records = UserData.objects.count()
    age_range = UserData.objects.aggregate(
        min_age=Min('age'),
        max_age=Max('age')
    )
    # Set defaults for min_age and max_age if None
    age_range['min_age'] = age_range.get('min_age') or 0
    age_range['max_age'] = age_range.get('max_age') or 0

    max_income = UserData.objects.aggregate(Max('income'))['income__max'] or 0
    average_income = UserData.objects.aggregate(Avg('income'))[
        'income__avg'] or 0
    records_by_gender = UserData.objects.values('gender').annotate(
        total=Count('gender')).order_by('gender')
    records_by_marital_status = UserData.objects.values('marital_status').annotate(
        total=Count('marital_status')).order_by('marital_status')
    records_by_education_level = UserData.objects.values('education_level').annotate(
        total=Count('education_level')).order_by('education_level')
    records_grouped_by_region = UserData.objects.values(
        'region').annotate(total=Count('region')).order_by('region')

    # Calculating the percentage for each region
    for record in records_grouped_by_region:
        record['percentage'] = (
            record['total'] / total_records * 100) if total_records > 0 else 0

    user_data_records = UserData.objects.all()

    return {
        'total_records': total_records,
        'age_range': age_range,
        'max_income': max_income,
        'average_income': average_income,
        'records_by_gender': records_by_gender,
        'records_by_marital_status': records_by_marital_status,
        'records_by_education_level': records_by_education_level,
        'records_grouped_by_region': records_grouped_by_region,
        'user_data_records': user_data_records,
    }


def fetch_enumerator_data():
    # Fetch all users except superusers
    users = User.objects.filter(
        is_superuser=False).prefetch_related('userprofile')

    # Fetch all roles
    roles = Role.objects.all()

    # Pass users and roles to the template
    return {
        'users': users,
        'roles': roles,
    }


@login_required
def enumerator_view_dashboard(request):
    return save_user_data(request)


def fetch_enumerator_dashboard_data(request):
    # Initialize the context dictionary with empty defaults
    context = {'user_data': [], 'user_data_count': 0}

    # Attempt to get all user data records associated with the current user
    user_data_qs = UserData.objects.filter(user=request.user)

    # Update the context dictionary with actual data if exists
    context['user_data'] = user_data_qs
    context['user_data_count'] = user_data_qs.count()

    return context


@login_required
def enumerator_view_search(request):
    user_profile = request.user.userprofile
    if user_profile.role.name == 'Enumerator':
        if request.method == 'POST' and request.FILES['image']:
            image = request.FILES['image']

            # Temporarily save the image
            fs = FileSystemStorage()
            filename = fs.save(image.name, image)
            image_path = fs.path(filename)

            # Extract face data from the uploaded image
            uploaded_face_data = extract_face_metadata(image_path)

            # Attempt to find a matching user
            user_data = None
            for face_metadata in FaceMetadata.objects.all():
                # Assuming the comparison logic
                if compare_faces(face_metadata.face_encoding, uploaded_face_data):
                    user_data = face_metadata.user_data
                    break

            # Clean up: delete the temporarily stored image
            os.remove(image_path)
            return render(request, 'agent/search.html', {'user_data': user_data})
        else:
            return render(request, 'agent/search.html', {'user_data': None})
    else:
        # Instead of redirecting to the login page, consider showing a 403 Forbidden page or redirecting to a safe page
        return HttpResponseForbidden("You are not authorized to view this page.")


def save_user_data(request):
    user_profile = request.user.userprofile
    if user_profile.role.name == 'Enumerator':
        if request.method == 'POST':
            user = request.user
            name = request.POST['name']
            phone = request.POST['phone']
            region = request.POST['region']
            gender = request.POST['gender']
            occupation = request.POST['occupation']
            education_level = request.POST['education_level']
            marital_status = request.POST['marital_status']
            income = request.POST['income']
            dependents = request.POST['dependents']
            age = request.POST['age']
            image = request.FILES['image']

            # Process the image file
            fs = FileSystemStorage()
            filename = fs.save(image.name, image)
            image_url = fs.url(filename)

            # Getting the absolute filesystem path of the saved image
            image_abs_path = os.path.join(settings.MEDIA_ROOT, filename)
            face_data = extract_face_metadata(image_abs_path)

            if face_data is None:
                messages.error(
                    request, "Invalid image. Your image must have only one clear face.")
            else:
                # Create UserData instance
                data = UserData.objects.create(
                    user=user,
                    name=name,
                    age=age,
                    phone=phone,
                    region=region,
                    gender=gender,
                    occupation=occupation,
                    education_level=education_level,
                    marital_status=marital_status,
                    income=income,
                    number_of_dependents=dependents,
                    image=image_url,
                )

                FaceMetadata.objects.create(
                    user_data=data,
                    face_encoding=face_data
                )

            messages.success(request, "New enumeration saved successfully")
            return redirect('enumerator-dashboard')

        data = fetch_enumerator_dashboard_data(request)
        return render(request, 'agent/dashboard.html', data)
    else:
        # Instead of redirecting to the login page, consider showing a 403 Forbidden page or redirecting to a safe page
        return HttpResponseForbidden("You are not authorized to view this page.")


@login_required
def enumerator_delete_enumeration_record(request, record_id):
    record = get_object_or_404(UserData, pk=record_id)
    # Check if the user is allowed to delete the record
    if request.user.is_authenticated and request.user == record.user:
        # If the object has an image field and an image is associated
        if record.image:
            # Construct the full file path
            filename = record.image.name.split('/')[-1]
            image_path = os.path.join(settings.MEDIA_ROOT, filename)
            # Delete the file if it exists
            if os.path.isfile(image_path):
                os.remove(image_path)
        record.delete()
        messages.success(request, 'Record deleted successfully.')
    else:
        messages.error(
            request, 'You do not have permission to delete this record.')
    return redirect(reverse('enumerator-dashboard'))


@login_required
def admin_delete_enumeration_record(request, record_id):
    record = get_object_or_404(UserData, pk=record_id)
    if request.user.is_authenticated:
        # If the object has an image field and an image is associated
        if record.image:
            # Construct the full file path
            filename = record.image.name.split('/')[-1]
            image_path = os.path.join(settings.MEDIA_ROOT, filename)
            # Delete the file if it exists
            if os.path.isfile(image_path):
                os.remove(image_path)
        record.delete()
        messages.success(request, 'Record deleted successfully.')
    else:
        messages.error(
            request, 'You do not have permission to delete this record.')
    return redirect(reverse('admin-dashboard'))


def logout_view(request):
    logout(request)
    return redirect('login')
