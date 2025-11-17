from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from .models import Staff
from .serializers import StaffSerializer 
from rest_framework_simplejwt.tokens import RefreshToken

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):

    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    name = request.data.get('name')
    shift = request.data.get('shift')
    phone_number = request.data.get('phone_number')
    role = request.data.get('role', 'staff')  

    if not username or not password or not email or not name:
        return Response({"error": "username, password, email, and name are required"}, status=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(email=email).exists():
        return Response({"error": "Email already exists"}, status=status.HTTP_400_BAD_REQUEST)
    

    try:
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            is_staff=(role == 'manager')
        )

        staff = Staff.objects.create(
            user=user,
            name=name,
            role=role,
            email=email
        )

       
        refresh = RefreshToken.for_user(user)
        serialized_staff_data = StaffSerializer(staff).data

      

        return Response({
            "message": "User registerd successfully",
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user_id": user.id,
            "username": user.username,
            "role": role,
            "staff_details": serialized_staff_data
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        print(f"Error registering user: {e}")
        return Response({"error": "An error occured during registration"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    print("--- DEBUG: Login View ---") # Debug log
    print(f"Request method: {request.method}") # Should be POST
    print(f"Request content type: {request.content_type}") # What Django sees
    print(f"Request META CONTENT_TYPE: {request.META.get('CONTENT_TYPE')}") # Raw header
    print(f"Request META HTTP_CONTENT_TYPE: {request.META.get('HTTP_CONTENT_TYPE')}") # Another way it might be stored
    print(f"Raw request body (as string): {request._request.body}") # Raw body from underlying Django request
    print(f"Type of request.data: {type(request.data)}") # Should be QueryDict-like for DRF
    print(f"Contents of request.data: {request.data}") # This is what's empty
    print(f"Keys in request.data: {list(request.data.keys()) if hasattr(request.data, 'keys') else 'N/A'}")
    print("--- END DEBUG ---") # Debug log

    if 'credentials' in request.data:
        credentials = request.data['credentials']
        username = credentials.get('username')
        password = credentials.get('password')
    else:
        username= request.data.get('username')
        password= request.data.get('password')

    

    print(f"Extracted username: {username}") # Debug log
    print(f"Extracted password: {password}") # Debug log

    if not username or not password:
        print("Error: Username or password missing in request.data") # Debug log
        return Response({"error": "username and password are required."}, status=status.HTTP_400_BAD_REQUEST)
    
    user = authenticate(request, username=username, password=password)

    if user is not None:
        login(request, user)

        refresh = RefreshToken.for_user(user)

        try:
            staff_profile = Staff.objects.get(user=user)
            staff_data = StaffSerializer(staff_profile).data
            role = staff_profile.role

        except Staff.DoesNotExist:
            staff_data = None
            role = "manager" if user.is_staff else "staff"

        return Response({
            "message": "login successful.",
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user_id": user.id,
            "username": user.username,
            "role": role,
            "staff_details": staff_data
        }, status=status.HTTP_200_OK)
    else:
        return Response({"error": "invalid username or password."}, status=status.HTTP_401_UNAUTHORIZED)
    



