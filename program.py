import math
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from geopy.geocoders import Nominatim

# Константи споживання пального
FUEL_CONSUMPTION = {
    'бензин': 8.5,  # л/100км
    'дизель': 6.5   # л/100км
}

# --- Формула гаверсинусів ---
def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Обчислює відстань між двома точками на сфері (Земля)
    за формулою гаверсинусів. Повертає відстань у кілометрах.
    """
    R = 6371.0  # Радіус Землі в км

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)

    c = 2 * math.asin(math.sqrt(a))

    return R * c

# --- Функція для отримання даних з CSV ---
@st.cache_data
def fetch_gas_stations_from_csv():
    try:
        df = pd.read_csv('gas_stations.csv')
        gas_stations = df[['id', 'name', 'latitude', 'longitude']].values.tolist()
        gas_stations_rating = dict(zip(df['name'], df['rating']))
        return gas_stations, gas_stations_rating
    except FileNotFoundError:
        st.error("""
        **Помилка: Файл 'gas_stations.csv' не знайдено.** Будь ласка, перевірте наявність файлу в папці з проєктом. 
        Структура даних має бути такою: `id, name, latitude, longitude, rating`
        """)
        return [], {}
    except Exception as e:
        st.error(f"Виникла технічна помилка: {e}")
        return [], {}

# Функція для обчислення необхідного палива
def calculate_fuel_needed(distance, fuel_consumption, motor_power):
    return (distance / 100) * fuel_consumption * motor_power

# Функція для генерації карти
def generate_map(user_location, gas_stations, fuel_needed_gas_station, max_distance):
    mymap = folium.Map(location=[user_location.latitude, user_location.longitude], zoom_start=13)

    # Додаємо коло радіусом максимального ходу (max_distance в км, множимо на 1000 для метрів)
    folium.Circle(
        radius=max_distance * 1000,
        location=[user_location.latitude, user_location.longitude],
        color="crimson",
        fill=True,
        fill_color="crimson",
        fill_opacity=0.1,
        popup=f"Ваша зона досяжності: {max_distance:.1f} км"
    ).add_to(mymap)

    folium.Marker(
        [user_location.latitude, user_location.longitude],
        popup="Ваше місцезнаходження",
        icon=folium.Icon(color='red')
    ).add_to(mymap)

    for station in gas_stations:
        for gas_station_info in fuel_needed_gas_station:
            if station[0] == gas_station_info[0]:
                rating = gas_station_info[3]

                popup_text = f"<b>Назва:</b> {station[1]}<br>"
                popup_text += f"<b>Рейтинг:</b> {rating}<br>"
                popup_text += f"<b>Необхідне паливо:</b> {gas_station_info[4]:.2f} літрів"

                if rating >= 8:
                    marker_color = 'green'
                elif rating >= 6:
                    marker_color = 'blue'
                else:
                    marker_color = 'orange'

                icon_html = f"""
                <div style="background-color: {marker_color}; color: white; text-align: center;
                            font-weight: bold; border-radius: 50%; width: 28px; height: 28px;
                            display: flex; align-items: center; justify-content: center; font-size: 12px;">
                    {rating}
                </div>"""

                folium.Marker(
                    [station[2], station[3]],
                    popup=folium.Popup(popup_text, max_width=200),
                    icon=folium.DivIcon(html=icon_html, icon_size=(28, 28))
                ).add_to(mymap)
                break

    folium_static(mymap)

# Основна функція
def main():
    st.title("Карта АЗС")
    st.sidebar.title("Пошук станцій")

    fuel_type = st.sidebar.selectbox("Оберіть тип палива:", ('Дизель', 'Бензин'))
    gas_left = st.sidebar.number_input("Введіть кількість пального в баку (л):", min_value=0.0, value=1.0)
    motor_power = st.sidebar.number_input("Введіть коефіцієнт об'єму двигуна:", min_value=0.1, value=1.0)
    location_str = st.sidebar.text_input("Введіть ваше місцезнаходження:", value="Львів, Університетська 1")

    if location_str:
        geolocator = Nominatim(user_agent="gas_station_locator_v5")
        user_location = geolocator.geocode(location_str)

        if user_location:
            gas_stations, gas_stations_rating = fetch_gas_stations_from_csv()

            if not gas_stations:
                st.warning("База заправок порожня.")
                return

            max_distance = (gas_left / FUEL_CONSUMPTION[fuel_type.lower()]) * 100

            # Використовуємо формулу гаверсинусів для обчислення відстані
            gas_stations_with_distances = []
            for station in gas_stations:
                dist = haversine_distance(
                    user_location.latitude, user_location.longitude,
                    station[2], station[3]
                )
                if dist <= max_distance:
                    gas_stations_with_distances.append((station[0], station[1], dist))

            sorted_gas_stations = sorted(gas_stations_with_distances, key=lambda x: x[2])

            st.sidebar.subheader("Найближчі заправки:")
            fuel_needed_gas_station = []

            for idx, (station_id, station_name, distance) in enumerate(sorted_gas_stations[:5], start=1):
                fuel_needed = calculate_fuel_needed(distance, FUEL_CONSUMPTION[fuel_type.lower()], motor_power)

                if fuel_needed <= gas_left:
                    rating = gas_stations_rating.get(station_name, 'Н/Д')
                    fuel_needed_gas_station.append((station_id, station_name, distance, rating, fuel_needed))

                    st.sidebar.write(f"{idx}. {station_name}")
                    st.sidebar.write(f"   - Відстань: {distance:.2f} км")
                    st.sidebar.write(f"   - Рейтинг: {rating}")
                    st.sidebar.write(f"   - Потрібно: {fuel_needed:.2f} л")

            if not fuel_needed_gas_station:
                generate_map(user_location, gas_stations, [], max_distance)
                st.sidebar.warning("⛽ Палива не вистачає до жодної заправки!")

                # Знаходимо найближчу заправку незалежно від запасу пального
                all_stations_with_dist = [
                    (station[0], station[1],
                     haversine_distance(
                         user_location.latitude, user_location.longitude,
                         station[2], station[3]
                     ),
                     station[2], station[3])
                    for station in gas_stations
                ]
                nearest = min(all_stations_with_dist, key=lambda x: x[2])

                # Середня швидкість пішки ~5 км/год
                walking_time_hours = nearest[2] / 5.0
                walking_minutes = int(walking_time_hours * 60)

                st.sidebar.info(
                    f"🚶 Найближча заправка: **{nearest[1]}**\n\n"
                    f"📍 Відстань пішки: **{nearest[2]:.2f} км**\n\n"
                    f"⏱️ Орієнтовний час: **{walking_minutes} хв**"
                )

                walking_url = (
                    f"https://www.google.com/maps/dir/?api=1"
                    f"&origin={user_location.latitude},{user_location.longitude}"
                    f"&destination={nearest[3]},{nearest[4]}"
                    f"&travelmode=walking"
                )
                st.sidebar.markdown(f"[🚶 МАРШРУТ ПІШКИ У GOOGLE MAPS]({walking_url})")
            else:
                generate_map(user_location, gas_stations, fuel_needed_gas_station, max_distance)

                options = [str(i) for i in range(1, len(fuel_needed_gas_station) + 1)]
                chosen_station = st.sidebar.selectbox("Виберіть номер АЗС:", options)

                if st.sidebar.button("Прокласти маршрут"):
                    selected_idx = int(chosen_station) - 1
                    info = fuel_needed_gas_station[selected_idx]

                    selected_data = next(s for s in gas_stations if s[0] == info[0])

                    directions_url = (
                        f"https://www.google.com/maps/dir/?api=1"
                        f"&origin={user_location.latitude},{user_location.longitude}"
                        f"&destination={selected_data[2]},{selected_data[3]}"
                        f"&travelmode=driving"
                    )
                    st.sidebar.markdown(f"[🚀 ВІДКРИТИ МАРШРУТ У GOOGLE MAPS]({directions_url})")

if __name__ == "__main__":
    main()
