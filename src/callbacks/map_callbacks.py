from dash import Input, Output, State

def register_map_callbacks(app):
    @app.callback(
        [Output('map-zoom-store', 'data'),
         Output('map-center-store', 'data')],
        [Input('route-map', 'relayoutData')],
        [State('map-zoom-store', 'data'),
         State('map-center-store', 'data')]
    )
    def update_zoom_and_center(relayoutData, current_zoom, current_center):
        new_zoom = current_zoom
        new_center = current_center

        if relayoutData:
            if 'mapbox.zoom' in relayoutData:
                new_zoom = relayoutData['mapbox.zoom']
            if 'mapbox.center' in relayoutData:
                new_center = {
                    'lat': relayoutData['mapbox.center']['lat'],
                    'lon': relayoutData['mapbox.center']['lon']
                }

        return new_zoom, new_center
