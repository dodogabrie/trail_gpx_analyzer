import plotly.graph_objects as go

from utils.data_filter import filter_df_by_range
from utils.stats_calculator import calculate_stats


def handle_hover(hoverData, df, fig_map_copy, current_zoom, current_center):
    point_index = hoverData['points'][0]['pointIndex']
    hover_lat = df.iloc[point_index]['Latitude']
    hover_lon = df.iloc[point_index]['Longitude']

    fig_map_copy.update_layout(
        mapbox=dict(
            style='open-street-map',
            zoom=current_zoom,
            center=current_center
        )
    )
    fig_map_copy.add_trace(go.Scattermapbox(
        lat=[hover_lat],
        lon=[hover_lon],
        mode='markers',
        marker=dict(size=10, color='red'),
        name="Hovered Point"
    ))

    return fig_map_copy


def handle_selection(selectedData, df, fig_map_copy, current_zoom, current_center):
    x_range = selectedData['range']['x']
    selected_df = filter_df_by_range(df, x_range)

    if not selected_df.empty:
        stats_text = calculate_stats(selected_df)

        # Highlight the selected segment on the map
        fig_map_copy.add_trace(go.Scattermapbox(
            lat=selected_df['Latitude'],
            lon=selected_df['Longitude'],
            mode='lines',
            line=dict(width=4, color='red'),
        ))
    else:
        stats_text = "No valid segment selected. Please try selecting a range on the elevation profile."

    fig_map_copy.update_layout(
        mapbox=dict(
            style='open-street-map',
            zoom=current_zoom,
            center=current_center
        )
    )

    return fig_map_copy, stats_text