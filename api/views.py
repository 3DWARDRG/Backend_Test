from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import TripInputSerializer
from .services import compute_trip
class TripCreateView(APIView):
    def post(self, request, format=None):
        serializer = TripInputSerializer(data=request.data)
        if serializer.is_valid():
            result = compute_trip(serializer.validated_data)
            return Response(result)
        return Response(serializer.errors, status=400)