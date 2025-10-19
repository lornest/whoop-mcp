"""
WHOOP Data Formatters

Functions to format WHOOP API responses into human-readable text.
"""


def format_workout(workout: dict) -> str:
    """Format a workout record into human-readable text."""
    lines = []

    # Header with sport name (prioritise over less user-friendly ID)
    sport = workout.get("sport_name", f"Sport ID {workout.get('sport_id', 'Unknown')}")
    start = workout.get("start", "")
    lines.append(f"Workout: {sport}")
    if start:
        lines.append(f"  Time: {start}")

    # Score data if available
    if workout.get("score_state") == "SCORED" and "score" in workout:
        score = workout["score"]
        if "strain" in score and score["strain"] is not None:
            lines.append(f"  Strain: {score['strain']}")
        if "average_heart_rate" in score and score["average_heart_rate"] is not None:
            lines.append(f"  Avg Heart Rate: {score['average_heart_rate']} bpm")
        if "max_heart_rate" in score and score["max_heart_rate"] is not None:
            lines.append(f"  Max Heart Rate: {score['max_heart_rate']} bpm")
        if "kilojoule" in score and score["kilojoule"] is not None:
            lines.append(f"  Energy: {score['kilojoule']} kJ")
        if "distance_meter" in score and score["distance_meter"] is not None:
            distance_km = score['distance_meter'] / 1000
            lines.append(f"  Distance: {distance_km:.2f} km")
        if "altitude_gain_meter" in score and score["altitude_gain_meter"] is not None:
            lines.append(f"  Altitude Gain: {score['altitude_gain_meter']} m")
        if "altitude_change_meter" in score and score["altitude_change_meter"] is not None:
            lines.append(f"  Altitude Change: {score['altitude_change_meter']} m")

    return "\n".join(lines)


def format_sleep(sleep: dict) -> str:
    """Format a sleep record into human-readable text."""
    lines = []

    # Header
    start = sleep.get("start", "")
    end = sleep.get("end", "")
    is_nap = sleep.get("nap", False)
    sleep_type = "Nap" if is_nap else "Sleep"
    lines.append(f"{sleep_type}: {start} to {end}")

    # Score data if available
    if sleep.get("score_state") == "SCORED" and "score" in sleep:
        score = sleep["score"]

        # Performance metrics
        if "sleep_performance_percentage" in score and score["sleep_performance_percentage"] is not None:
            lines.append(f"  Performance: {score['sleep_performance_percentage']}%")
        if "sleep_efficiency_percentage" in score and score["sleep_efficiency_percentage"] is not None:
            lines.append(f"  Efficiency: {score['sleep_efficiency_percentage']}%")
        if "respiratory_rate" in score and score["respiratory_rate"] is not None:
            lines.append(f"  Respiratory Rate: {score['respiratory_rate']} breaths/min")

        # Stage breakdown
        if "stage_summary" in score and score["stage_summary"] is not None:
            stages = score["stage_summary"]
            if "total_in_bed_time_milli" in stages and stages["total_in_bed_time_milli"] is not None:
                total_mins = stages["total_in_bed_time_milli"] / 1000 / 60
                lines.append(f"  Total Time in Bed: {total_mins:.0f} minutes")
            if "total_awake_time_milli" in stages and stages["total_awake_time_milli"] is not None:
                awake_mins = stages["total_awake_time_milli"] / 1000 / 60
                lines.append(f"  Awake Time: {awake_mins:.0f} minutes")
            if "total_light_sleep_time_milli" in stages and stages["total_light_sleep_time_milli"] is not None:
                light_mins = stages["total_light_sleep_time_milli"] / 1000 / 60
                lines.append(f"  Light Sleep: {light_mins:.0f} minutes")
            if "total_slow_wave_sleep_time_milli" in stages and stages["total_slow_wave_sleep_time_milli"] is not None:
                deep_mins = stages["total_slow_wave_sleep_time_milli"] / 1000 / 60
                lines.append(f"  Deep Sleep: {deep_mins:.0f} minutes")
            if "total_rem_sleep_time_milli" in stages and stages["total_rem_sleep_time_milli"] is not None:
                rem_mins = stages["total_rem_sleep_time_milli"] / 1000 / 60
                lines.append(f"  REM Sleep: {rem_mins:.0f} minutes")

    return "\n".join(lines)


def format_recovery(recovery: dict) -> str:
    """Format a recovery record into human-readable text."""
    lines = []

    # Header
    created = recovery.get("created_at", "")
    lines.append(f"Recovery: {created}")

    # Score data if available
    if recovery.get("score_state") == "SCORED" and "score" in recovery:
        score = recovery["score"]

        if "recovery_score" in score and score["recovery_score"] is not None:
            lines.append(f"  Recovery Score: {score['recovery_score']}%")
        if "resting_heart_rate" in score and score["resting_heart_rate"] is not None:
            lines.append(f"  Resting Heart Rate: {score['resting_heart_rate']} bpm")
        if "hrv_rmssd_milli" in score and score["hrv_rmssd_milli"] is not None:
            hrv = score["hrv_rmssd_milli"]
            lines.append(f"  HRV: {hrv:.1f} ms")
        if "spo2_percentage" in score and score["spo2_percentage"] is not None:
            lines.append(f"  SpO2: {score['spo2_percentage']}%")
        if "skin_temp_celsius" in score and score["skin_temp_celsius"] is not None:
            lines.append(f"  Skin Temperature: {score['skin_temp_celsius']:.1f}°C")

    return "\n".join(lines)


def format_cycle(cycle: dict) -> str:
    """Format a cycle record into human-readable text."""
    lines = []

    # Header
    start = cycle.get("start", "")
    end = cycle.get("end", "In Progress")
    lines.append(f"Cycle: {start} to {end}")

    # Score data if available
    if cycle.get("score_state") == "SCORED" and "score" in cycle:
        score = cycle["score"]

        if "strain" in score and score["strain"] is not None:
            lines.append(f"  Strain: {score['strain']}")
        if "kilojoule" in score and score["kilojoule"] is not None:
            lines.append(f"  Energy: {score['kilojoule']} kJ")
        if "average_heart_rate" in score and score["average_heart_rate"] is not None:
            lines.append(f"  Avg Heart Rate: {score['average_heart_rate']} bpm")
        if "max_heart_rate" in score and score["max_heart_rate"] is not None:
            lines.append(f"  Max Heart Rate: {score['max_heart_rate']} bpm")

    return "\n".join(lines)


def format_response(data: dict, formatter_func) -> str:
    """Format API response data using a specific formatter function."""
    if "records" in data:
        # Multiple records
        records = data["records"]
        if not records:
            return "No records found."

        formatted_records = [formatter_func(record) for record in records]
        result = "\n\n".join(formatted_records)

        # Add pagination info if available
        if "next_token" in data:
            result += "\n\n(More records available - use pagination)"

        return result
    else:
        # Single record or direct data
        return formatter_func(data)
