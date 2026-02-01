"""
MongoDB document schema context for Apple Health data.
Provides schema information to all agents for accurate NL→MQL queries.
"""

MONGODB_SCHEMA_CONTEXT = """
## Apple Health Data MongoDB Schema

The health data is stored in MongoDB with the following document structure.
Each document represents a daily health summary for a user.

### Document Structure

```json
{
  "_id": ObjectId,
  "date": ISODate,           // The date this record represents (YYYY-MM-DD)
  "user_id": String,         // User identifier
  
  // ============ ACTIVITY DATA ============
  "activity": {
    "steps": Number,                    // Total steps for the day
    "distance_km": Number,              // Total distance in kilometers
    "flights_climbed": Number,          // Floors/flights climbed
    "active_energy_burned_kcal": Number, // Active calories burned
    "basal_energy_burned_kcal": Number,  // Resting calories burned
    "exercise_minutes": Number,          // Minutes of exercise
    "stand_hours": Number,               // Hours with standing activity
    "move_minutes": Number,              // Movement minutes
    "workouts": [                        // Array of workout sessions
      {
        "type": String,                  // "running", "walking", "cycling", "strength", etc.
        "start_time": ISODate,
        "end_time": ISODate,
        "duration_minutes": Number,
        "distance_km": Number,
        "energy_burned_kcal": Number,
        "average_heart_rate": Number,
        "max_heart_rate": Number
      }
    ]
  },
  
  // ============ SLEEP DATA ============
  "sleep": {
    "in_bed_seconds": Number,           // Total time in bed
    "asleep_seconds": Number,           // Total time asleep
    "sleep_efficiency": Number,         // Percentage (0-100)
    "bed_time": ISODate,                // When went to bed
    "wake_time": ISODate,               // When woke up
    "stages": {
      "deep_seconds": Number,           // Deep sleep duration
      "core_seconds": Number,           // Core/light sleep duration  
      "rem_seconds": Number,            // REM sleep duration
      "awake_seconds": Number           // Awake time during sleep
    },
    "sleep_score": Number               // Overall sleep score (0-100)
  },
  
  // ============ HEART DATA ============
  "heart": {
    "resting_heart_rate": Number,       // Resting HR in bpm
    "average_heart_rate": Number,       // Daily average HR
    "max_heart_rate": Number,           // Maximum HR recorded
    "min_heart_rate": Number,           // Minimum HR recorded
    "hrv_average_ms": Number,           // Heart Rate Variability in ms
    "hrv_readings": [                   // Individual HRV readings
      {
        "timestamp": ISODate,
        "value_ms": Number
      }
    ],
    "walking_heart_rate_avg": Number,   // Average HR while walking
    "cardio_fitness_vo2max": Number     // VO2 max estimate
  },
  
  // ============ BODY MEASUREMENTS ============
  "body": {
    "weight_kg": Number,
    "height_cm": Number,
    "bmi": Number,
    "body_fat_percentage": Number,
    "lean_body_mass_kg": Number,
    "waist_circumference_cm": Number
  },
  
  // ============ VITALS ============
  "vitals": {
    "blood_pressure": {
      "systolic": Number,               // mmHg
      "diastolic": Number               // mmHg
    },
    "blood_oxygen_percentage": Number,  // SpO2
    "respiratory_rate": Number,         // Breaths per minute
    "body_temperature_celsius": Number
  },
  
  // ============ NUTRITION ============
  "nutrition": {
    "calories_consumed": Number,
    "protein_g": Number,
    "carbohydrates_g": Number,
    "fat_g": Number,
    "fiber_g": Number,
    "sugar_g": Number,
    "sodium_mg": Number,
    "water_ml": Number,
    "caffeine_mg": Number
  },
  
  // ============ MINDFULNESS ============
  "mindfulness": {
    "mindful_minutes": Number,
    "sessions": [
      {
        "type": String,                 // "meditation", "breathing", etc.
        "duration_minutes": Number,
        "timestamp": ISODate
      }
    ]
  },
  
  // ============ MENSTRUAL CYCLE (if applicable) ============
  "cycle": {
    "phase": String,                    // "menstrual", "follicular", "ovulation", "luteal"
    "day_of_cycle": Number,
    "symptoms": [String],
    "flow": String                      // "light", "medium", "heavy"
  },
  
  // ============ METADATA ============
  "metadata": {
    "data_sources": [String],           // ["apple_watch", "iphone", "manual"]
    "last_sync": ISODate,
    "timezone": String
  }
}
```

### Common Query Patterns

1. **Time-based filtering**: Always use `date` field for date ranges
2. **Nested field access**: Use dot notation (e.g., `sleep.asleep_seconds`)
3. **Array operations**: Use `$unwind` for workout/session analysis
4. **Aggregations**: Group by date for trends, use `$avg`, `$sum`, `$min`, `$max`

### Important Notes

- Not all fields are present in every document (sparse data)
- `date` is the primary field for time-series queries
- Sleep data's `bed_time` may be from the previous day (overnight sleep)
- HRV readings may have multiple entries per day
- Workout types are lowercase strings
"""

FIELD_MAPPING = {
    # Common natural language to field mappings
    "sleep": "sleep",
    "sleep hours": "sleep.asleep_seconds",
    "time asleep": "sleep.asleep_seconds", 
    "deep sleep": "sleep.stages.deep_seconds",
    "rem sleep": "sleep.stages.rem_seconds",
    "sleep quality": "sleep.sleep_score",
    "sleep efficiency": "sleep.sleep_efficiency",
    
    "steps": "activity.steps",
    "walking": "activity.distance_km",
    "exercise": "activity.exercise_minutes",
    "workouts": "activity.workouts",
    "calories burned": "activity.active_energy_burned_kcal",
    "active calories": "activity.active_energy_burned_kcal",
    
    "heart rate": "heart.resting_heart_rate",
    "resting heart rate": "heart.resting_heart_rate",
    "hrv": "heart.hrv_average_ms",
    "heart rate variability": "heart.hrv_average_ms",
    "vo2 max": "heart.cardio_fitness_vo2max",
    
    "weight": "body.weight_kg",
    "bmi": "body.bmi",
    "body fat": "body.body_fat_percentage",
    
    "blood pressure": "vitals.blood_pressure",
    "blood oxygen": "vitals.blood_oxygen_percentage",
    "spo2": "vitals.blood_oxygen_percentage",
    
    "water": "nutrition.water_ml",
    "calories eaten": "nutrition.calories_consumed",
    "protein": "nutrition.protein_g",
    
    "meditation": "mindfulness.mindful_minutes",
    "mindfulness": "mindfulness.mindful_minutes",
}
