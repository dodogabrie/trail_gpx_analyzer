def calculate_stats(selected_df):
    delta_elev = selected_df['Elevation'].diff().fillna(0)
    d_plus = delta_elev[delta_elev > 0].sum()
    d_minus = -delta_elev[delta_elev < 0].sum()
    total_distance = selected_df['Distance'].iloc[-1] - selected_df['Distance'].iloc[0]

    stats_text = f'''
    **Selected Segment Stats:**

    - Distance: {total_distance / 1000:.2f} km
    - Elevation Gain (D+): {d_plus:.2f} m
    - Elevation Loss (D-): {d_minus:.2f} m
    '''
    return stats_text
