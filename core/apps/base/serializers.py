from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=300, required=True)
    password = serializers.CharField(required=True, write_only=True)


class AuthUserSerializer(serializers.ModelSerializer):
    # auth_token = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff',)
        read_only_fields = ('id', 'is_active', 'is_staff')

    # def get_auth_token(self, obj):
    #     token = Token.objects.create(user=obj)
    #     return token.key


class EmptySerializer(serializers.Serializer):
    pass
