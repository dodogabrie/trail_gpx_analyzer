def filter_df_by_range(df, x_range):
    return df[(df['Distance'] >= x_range[0]) & (df['Distance'] <= x_range[1])]