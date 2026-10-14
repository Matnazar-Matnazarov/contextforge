from rest_framework import serializers

from .models import Membership, Organization, Role


class OrganizationSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "role", "created_at"]
        read_only_fields = ["id", "role", "created_at"]

    def get_role(self, obj) -> str | None:
        roles = self.context.get("roles", {})
        return roles.get(obj.id)


class MembershipSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    display_name = serializers.CharField(source="user.display_name", read_only=True)
    user_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user_id", "email", "display_name", "role", "status", "created_at"]
        read_only_fields = fields


class AddMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Role.choices, default=Role.MEMBER)


class ChangeRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)
