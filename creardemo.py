schema_info = {
  "races": {
    "description": "Contiene información sobre cada Gran Premio, incluyendo la fecha, ubicación, número de ronda y año.",
    "columns": {
      "race_id": "Identificador único de la carrera.",
      "year": "Año en que se realizó la carrera.",
      "round": "Número de ronda del campeonato en ese año.",
      "date": "Fecha de la carrera.",
      "time": "Hora de inicio de la carrera.",
      "circuit_id": "Identificador del circuito donde se realizó la carrera."
    }
  },
  "circuits": {
    "description": "Información sobre los circuitos de carrera.",
    "columns": {
      "circuit_id": "Identificador único del circuito.",
      "circuit_ref": "Referencia textual del circuito.",
      "location": "Ciudad donde se encuentra el circuito.",
      "country": "País donde se encuentra el circuito."
    }
  },
  "drivers": {
    "description": "Datos personales de los pilotos.",
    "columns": {
      "driver_id": "Identificador único del piloto.",
      "forename": "Nombre del piloto.",
      "surname": "Apellido del piloto.",
      "code": "Código abreviado del piloto.",
      "nationality": "Nacionalidad del piloto."
    }
  },
  "constructors": {
    "description": "Información sobre los equipos de Fórmula 1.",
    "columns": {
      "constructor_id": "Identificador único del constructor.",
      "name": "Nombre del equipo o constructor.",
      "nationality": "Nacionalidad del constructor."
    }
  },
  "results": {
    "description": "Resultados individuales de cada piloto en cada carrera.",
    "columns": {
      "result_id": "Identificador único del resultado.",
      "race_id": "Identificador de la carrera.",
      "driver_id": "Identificador del piloto.",
      "constructor_id": "Identificador del constructor o equipo.",
      "grid": "Posición de salida en la parrilla.",
      "position": "Posición final en la carrera.",
      "points": "Puntos obtenidos en esa carrera.",
      "fastest_lap": "Vuelta más rápida del piloto.",
      "fastest_lap_time": "Tiempo de la vuelta más rápida.",
      "fastest_lap_speed": "Velocidad de la vuelta más rápida.",
      "dnf": "Indica si el piloto no terminó la carrera (true/false).",
      "position_change": "Cantidad de posiciones ganadas o perdidas durante la carrera."
    }
  },
  "weather": {
    "description": "Condiciones climáticas durante las carreras.",
    "columns": {
      "weather_id": "Identificador del registro climático.",
      "race_id": "Identificador de la carrera.",
      "temperature_C": "Temperatura promedio en grados Celsius.",
      "precipitation_mm": "Precipitaciones acumuladas en milímetros.",
      "wind_speed_kmh": "Velocidad del viento en km/h.",
      "humidity_pct": "Porcentaje de humedad.",
      "is_rainy": "Indica si hubo lluvia durante la carrera (true/false)."
    }
  },
  "driver_stats": {
    "description": "Estadísticas derivadas por piloto en una carrera.",
    "columns": {
      "driver_stat_id": "Identificador del registro estadístico.",
      "race_id": "Identificador de la carrera.",
      "driver_id": "Identificador del piloto.",
      "avg_gap_to_team": "Diferencia promedio con respecto a su compañero de equipo.",
      "avg_gap_to_leader": "Diferencia promedio con el líder de la carrera.",
      "avg_points": "Promedio de puntos por carrera.",
      "total_points": "Puntos acumulados hasta esa carrera.",
      "avg_real_points": "Promedio de puntos considerando abandono de rivales.",
      "dnf_rate": "Tasa de abandono del piloto.",
      "win_rate": "Tasa de victorias del piloto."
    }
  },
  "driver_series": {
    "description": "Estadísticas en series móviles (últimas N carreras) para cada piloto.",
    "columns": {
      "driver_series_id": "Identificador del registro de serie.",
      "race_id": "Identificador de la carrera.",
      "driver_id": "Identificador del piloto.",
      "last_n_avg_position": "Posición promedio en las últimas N carreras.",
      "last_n_total_points": "Total de puntos en las últimas N carreras.",
      "last_n_wins": "Cantidad de victorias en las últimas N carreras.",
      "last_n_dnfs": "Cantidad de abandonos en las últimas N carreras.",
      "last_n_avg_gap_to_team": "Promedio de diferencia con el compañero en las últimas N."
    }
  }
}

from db import register_tenant_database
from models import Tenant, TenantDatabase, Base
from db import get_admin_session

# Esto borra y recrea toda la tabla
Base.metadata.drop_all(bind=admin_engine)
Base.metadata.create_all(bind=admin_engine)

db = get_admin_session()
t = Tenant (name = "demo_empresa")
db.add(t)
db.flush()
td = TenantDatabase(
    tenant_name = t.name,
    base_name = "f1",
    schema_info = schema_info,
    db_path = "./data/f1_tenant.db" 
)
db.add(td)
db.commit()
db.close()