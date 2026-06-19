from rest_framework import serializers
from .models import Trip

class TripInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ['current_location', 'pickup_location', 'dropoff_location', 'current_cycle_used']