import requests
from datetime import datetime, timedelta , time
import os

# ⚠️ PON AQUÍ TU API KEY REAL DE OPENROUTESERVICE
ORS_API_KEY = os.environ.get("ORS_API_KEY")

# ------------------------------------------------------------
# 1. Obtener ruta real desde OpenRouteService
# ------------------------------------------------------------
def get_route(origin, pickup, destination):
    city_coords = {
        "NY": [-74.0060, 40.7128],
        "Chicago": [-87.6298, 41.8781],
        "LA": [-118.2437, 34.0522],
        "Houston": [-95.3698, 29.7604],
        "Miami": [-80.1918, 25.7617],
        "Seattle": [-122.3321, 47.6062],
        "Denver": [-104.9903, 39.7392],
    }

    waypoints = []
    for loc in [origin, pickup, destination]:
        if isinstance(loc, str) and loc in city_coords:
            waypoints.append(city_coords[loc])
        else:
            waypoints.append(loc if isinstance(loc, list) else [-74.0060, 40.7128])

    body = {"coordinates": waypoints}
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json"
    }

    print("Consultando ORS con body:", body)

    try:
        resp = requests.post(
            "https://api.openrouteservice.org/v2/directions/driving-car",
            json=body,
            headers=headers,
            timeout=10
        )
        print("Status code:", resp.status_code)
        data = resp.json()

        if "error" in data:
            raise Exception(f"Error de ORS: {data['error']}")
        if "features" not in data:
            raise Exception(f"Respuesta inesperada: {data}")

        segment = data['features'][0]['properties']['segments'][0]
        distance_miles = segment['distance'] / 1609.34
        duration_hours = segment['duration'] / 3600
        geometry = data['features'][0]['geometry']
        return distance_miles, duration_hours, geometry

    except requests.exceptions.RequestException as e:
        print("Error de conexión:", e)
        return mock_route(origin, pickup, destination)
    except Exception as e:
        print("Error procesando respuesta:", e)
        return mock_route(origin, pickup, destination)

# ------------------------------------------------------------
# 2. Mock de ruta por si la API falla
# ------------------------------------------------------------
def mock_route(origin, pickup, destination):
    distances = {
        ("NY", "Chicago"): 790,
        ("Chicago", "LA"): 2015,
        ("NY", "LA"): 2790,
    }
    total = 0
    total += distances.get((origin, pickup), 800)
    total += distances.get((pickup, destination), 2000)
    duration = total / 55

    city_coords = {
        "NY": [-74.0060, 40.7128],
        "Chicago": [-87.6298, 41.8781],
        "LA": [-118.2437, 34.0522],
        "Houston": [-95.3698, 29.7604],
        "Miami": [-80.1918, 25.7617],
        "Seattle": [-122.3321, 47.6062],
        "Denver": [-104.9903, 39.7392],
    }
    def get_ll(loc):
        return city_coords.get(loc, [-74,40])

    geometry = {
        "type": "LineString",
        "coordinates": [get_ll(origin), get_ll(pickup), get_ll(destination)]
    }
    return total, duration, geometry

# ------------------------------------------------------------
# 3. Lógica principal: calcular todo el viaje
# ------------------------------------------------------------
def compute_trip(data):
    # 3.1 Obtener ruta
    distance_miles, driving_time_hours, geometry = get_route(
        data['current_location'],
        data['pickup_location'],
        data['dropoff_location']
    )

    # 3.2 Configuración del ciclo
    total_cycle_limit = 70
    current_cycle_used = float(data['current_cycle_used'])
    remaining_cycle = total_cycle_limit - current_cycle_used

    pickup_duration = 1.0
    dropoff_duration = 1.0
    fuel_duration = 0.5
    fuel_distance_max = 1000
    avg_speed = 55

    start_time = datetime(2026, 6, 16, 8, 0)
    current_time = start_time
    stops = []
    logs = []
    day_number = 1

    # 3.3 Pickup
    stops.append({
        "type": "pickup",
        "location": data['pickup_location'],
        "arrival_time": current_time.isoformat(),
        "departure_time": (current_time + timedelta(hours=pickup_duration)).isoformat(),
        "day": day_number
    })
    current_time += timedelta(hours=pickup_duration)
    remaining_cycle -= pickup_duration

    last_fuel_distance = 0.0
    driving_remaining = driving_time_hours

    # 3.4 Bucle de días
    while driving_remaining > 0:
        day_driving_hours = 0.0
        day_on_duty_hours = 0.0
        day_activities = []

        while (day_driving_hours < 11 and
               day_on_duty_hours < 14 and
               remaining_cycle > 0 and
               driving_remaining > 0):

            available_driving = min(11 - day_driving_hours, driving_remaining)
            available_duty = 14 - day_on_duty_hours
            max_by_cycle = remaining_cycle
            segment_drive_hours = min(available_driving, available_duty, max_by_cycle)
            if segment_drive_hours <= 0:
                break

            segment_distance = segment_drive_hours * avg_speed
            fuel_break_needed = False
            if last_fuel_distance + segment_distance >= fuel_distance_max:
                distance_before_fuel = fuel_distance_max - last_fuel_distance
                segment_drive_hours = distance_before_fuel / avg_speed
                if segment_drive_hours <= 0:
                    break
                fuel_break_needed = True

            drive_start = current_time
            drive_end = current_time + timedelta(hours=segment_drive_hours)
            day_activities.append({
                "type": "driving",
                "start_time": drive_start.time().strftime("%H:%M"),
                "end_time": drive_end.time().strftime("%H:%M")
            })
            day_driving_hours += segment_drive_hours
            day_on_duty_hours += segment_drive_hours
            remaining_cycle -= segment_drive_hours
            driving_remaining -= segment_drive_hours
            last_fuel_distance += segment_drive_hours * avg_speed
            current_time = drive_end

            if fuel_break_needed and last_fuel_distance >= fuel_distance_max - 1:
                if (day_on_duty_hours + fuel_duration <= 14) and (remaining_cycle >= fuel_duration):
                    fuel_start = current_time
                    fuel_end = current_time + timedelta(hours=fuel_duration)
                    day_activities.append({
                        "type": "on_duty",
                        "start_time": fuel_start.time().strftime("%H:%M"),
                        "end_time": fuel_end.time().strftime("%H:%M")
                    })
                    day_on_duty_hours += fuel_duration
                    remaining_cycle -= fuel_duration
                    stops.append({
                        "type": "fuel",
                        "location": "Interpolated",
                        "arrival_time": fuel_start.isoformat(),
                        "departure_time": fuel_end.isoformat(),
                        "day": day_number
                    })
                    current_time = fuel_end
                    last_fuel_distance = 0.0
                else:
                    break

        if driving_remaining <= 0:
            if (day_on_duty_hours + dropoff_duration <= 14) and (remaining_cycle >= dropoff_duration):
                drop_start = current_time
                drop_end = current_time + timedelta(hours=dropoff_duration)
                day_activities.append({
                    "type": "on_duty",
                    "start_time": drop_start.time().strftime("%H:%M"),
                    "end_time": drop_end.time().strftime("%H:%M")
                })
                day_on_duty_hours += dropoff_duration
                remaining_cycle -= dropoff_duration
                stops.append({
                    "type": "dropoff",
                    "location": data['dropoff_location'],
                    "arrival_time": drop_start.isoformat(),
                    "departure_time": drop_end.isoformat(),
                    "day": day_number
                })
                current_time = drop_end

        # Agregar descanso de 10h (puede cruzar medianoche)
        rest_start = current_time
        rest_end = current_time + timedelta(hours=10)
        day_activities.append({
            "type": "sleeper",
            "start_time": rest_start.time().strftime("%H:%M"),
            "end_time": rest_end.time().strftime("%H:%M")
        })

        # ----- NUEVO: dividir actividades que cruzan medianoche -----
        split_activities = []
        for act in day_activities:
            t_start = time.fromisoformat(act['start_time'])
            t_end = time.fromisoformat(act['end_time'])
            if t_end < t_start:  # cruza medianoche
                # Parte 1: hasta las 24:00
                split_activities.append({
                    'type': act['type'],
                    'start_time': act['start_time'],
                    'end_time': '24:00'
                })
                # Parte 2: desde 00:00 hasta end
                split_activities.append({
                    'type': act['type'],
                    'start_time': '00:00',
                    'end_time': act['end_time']
                })
            else:
                split_activities.append(act)
        day_activities = split_activities
        # ------------------------------------------------------------

        # Convertir a horas decimales para el frontend
        activities_decimal = []
        for act in day_activities:
            def time_str_to_decimal(t_str):
                h, m = map(int, t_str.split(':'))
                return h + m / 60.0
            start_dec = time_str_to_decimal(act['start_time'])
            end_dec = time_str_to_decimal(act['end_time'])
            activities_decimal.append({
                "type": act["type"],
                "start_hour": start_dec,
                "end_hour": end_dec
            })

        logs.append({
            "day": day_number,
            "date": rest_start.date().isoformat(),
            "activities": activities_decimal
        })

        current_time = rest_end
        day_number += 1

    # Asegurar dropoff si no se añadió
    if not any(stop['type'] == 'dropoff' for stop in stops):
        if remaining_cycle >= dropoff_duration:
            drop_start = current_time
            drop_end = current_time + timedelta(hours=dropoff_duration)
            # También puede cruzar medianoche, pero por simplicidad lo dejamos así (no debería ocurrir)
            logs.append({
                "day": day_number,
                "date": drop_start.date().isoformat(),
                "activities": [{
                    "type": "on_duty",
                    "start_hour": drop_start.hour + drop_start.minute/60,
                    "end_hour": drop_end.hour + drop_end.minute/60
                }]
            })
            stops.append({
                "type": "dropoff",
                "location": data['dropoff_location'],
                "arrival_time": drop_start.isoformat(),
                "departure_time": drop_end.isoformat(),
                "day": day_number
            })

    # --- Interpolación lineal simple para coordenadas de paradas ---
    route_coords = geometry['coordinates']  # lista de [lng, lat]
    cumulative_dist = [0.0]
    for i in range(1, len(route_coords)):
        dx = (route_coords[i][0] - route_coords[i-1][0]) * 69.0
        dy = (route_coords[i][1] - route_coords[i-1][1]) * 69.0
        seg_dist = (dx**2 + dy**2)**0.5
        cumulative_dist.append(cumulative_dist[-1] + seg_dist)
    total_dist_approx = cumulative_dist[-1] if cumulative_dist[-1] > 0 else 1

    def coord_at_distance(dist):
        if dist <= 0:
            return route_coords[0]
        for i in range(1, len(route_coords)):
            if dist <= cumulative_dist[i]:
                ratio = (dist - cumulative_dist[i-1]) / (cumulative_dist[i] - cumulative_dist[i-1])
                lng = route_coords[i-1][0] + (route_coords[i][0] - route_coords[i-1][0]) * ratio
                lat = route_coords[i-1][1] + (route_coords[i][1] - route_coords[i-1][1]) * ratio
                return [lng, lat]
        return route_coords[-1]

    fuel_count = 0
    for stop in stops:
        if stop['type'] == 'fuel':
            fuel_count += 1
            approx_dist = min(fuel_count * 1000.0, distance_miles)
            stop['coords'] = coord_at_distance(approx_dist)
        elif stop['type'] == 'pickup':
            stop['coords'] = coord_at_distance(0)
        elif stop['type'] == 'dropoff':
            stop['coords'] = coord_at_distance(distance_miles)

    return {
        "route": geometry,
        "stops": stops,
        "daily_logs": logs,
        "distance_miles": round(distance_miles, 2),
        "estimated_time_hours": round(driving_time_hours, 2)
    }