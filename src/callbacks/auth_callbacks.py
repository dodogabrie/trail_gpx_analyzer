from flask import session
from dash import Input, Output

def register_auth_callbacks(app):
    @app.callback(
        Output('auth-code-store', 'data'),
        Input('url', 'search')
    )
    def extract_auth_code_from_url(search):
        if search:
            query_params = dict(qc.split('=') for qc in search.lstrip('?').split('&'))
            return query_params.get('auth_code', '')
        return ''

    @app.callback(
        Output('auth-code', 'value'),
        Input('auth-button', 'n_clicks')
    )
    def update_auth_code(n_clicks):
        if n_clicks > 0:
            return session.get('auth_code', '')
        return ''
