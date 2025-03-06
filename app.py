from flask import Flask, render_template, request, session, url_for, redirect
import requests
import pandas as pd
import plotly.graph_objs as go
import plotly.offline as pyo
import math
import logging
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your_secret_key")  # Use environment variable

STATIONS_API = "https://environment.data.gov.uk/flood-monitoring/id/stations"
READINGS_PER_PAGE = 10

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_stations():
    try:
        response = requests.get(STATIONS_API)
        response.raise_for_status()
        data = response.json()
        return {s["notation"]: s["label"] for s in data.get("items", [])}
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching stations: {e}")
        return {}

def get_station_readings_24hr(station_id):
    url = f'https://environment.data.gov.uk/flood-monitoring/id/stations/{station_id}/readings'
    try:
        response = requests.get(url)
        response.raise_for_status()
        reading = response.json()
        reading = pd.DataFrame(reading['items'])

        reading['dateTime'] = pd.to_datetime(reading['dateTime'])
        reading['date'] = reading['dateTime'].dt.date
        reading_last_24_hr = reading[reading['date'] == reading['date'].iloc[0]]
        station_readings = reading_last_24_hr[['dateTime', 'value']].copy()
        station_readings = station_readings.sort_values(by='dateTime')

        return station_readings

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error fetching readings: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error fetching readings: {e}")
        return None
    except (KeyError, ValueError, IndexError) as e:
        logging.error(f"Data processing error: {e}")
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    stations = get_stations()
    selected_station = request.form.get('station') or session.get('selected_station')
    page = request.args.get('page', 1, type=int)

    if request.method == 'POST' and selected_station:
        session['selected_station'] = selected_station
        return redirect(url_for('index')) #redirect to prevent form resubmission

    plot_div = None
    table_html = None
    pagination = None
    error_message = None

    if selected_station:
        readings = get_station_readings_24hr(selected_station)

        if readings is not None and not readings.empty:
            trace = go.Scatter(x=readings['dateTime'], y=readings['value'], mode='lines', name='Water Levels')
            layout = go.Layout(
                title=f'Water Levels for {stations.get(selected_station, "Unknown Station")}',
                xaxis=dict(title='Time', gridcolor='lightgray'),
                yaxis=dict(title='Water Levels', gridcolor='lightgray'),
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(family='Arial, sans-serif'),
            )
            fig = go.Figure(data=[trace], layout=layout)
            plot_div = pyo.plot(fig, output_type='div')

            total_readings = len(readings)
            total_pages = math.ceil(total_readings / READINGS_PER_PAGE)
            start_index = (page - 1) * READINGS_PER_PAGE
            end_index = start_index + READINGS_PER_PAGE
            paged_readings = readings.iloc[start_index:end_index].copy()
            paged_readings['dateTime'] = paged_readings['dateTime'].dt.strftime('%Y-%m-%d %H:%M')
            table_html = paged_readings.rename(columns={'dateTime': 'Time Stamps', 'value': 'Water Levels'}).to_html(classes='table table-striped table-bordered', index=False)

            pagination = {
                'page': page,
                'total_pages': total_pages,
                'selected_station': selected_station,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'prev_page': page - 1,
                'next_page': page + 1
            }
        else:
            error_message = "No readings available for the selected station."
    elif selected_station and stations.get(selected_station) is None:
        error_message = "Station not found."

    return render_template('index.html', stations=stations, selected_station=selected_station, plot_div=plot_div, table_html=table_html, pagination=pagination, error_message=error_message)

if __name__ == '__main__':
    app.run(debug=True)