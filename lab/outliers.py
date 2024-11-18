import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from sklearn.linear_model import RANSACRegressor, LinearRegression
from sklearn.preprocessing import StandardScaler, PolynomialFeatures

def load_data(filepath):
    """
    Load the dataset and preprocess it.
    """
    df = pd.read_csv(filepath)

    # Convert velocity_smooth to min/km if not already done
    if df['velocity_smooth'].max() > 30:  # Assuming min/km won't exceed 30
        df['velocity_smooth'] = df['velocity_smooth'] * 3.6

    # Drop rows with missing values in relevant columns
    df.dropna(subset=['grade_smooth', 'velocity_smooth'], inplace=True)

    return df

def fit_robust_regression(df, degree=2):
    """
    Fit a RANSAC regression model with polynomial features to identify the trend and outliers.

    Returns:
    - inlier_mask: Boolean mask of inliers
    - outlier_mask: Boolean mask of outliers
    - model: Trained RANSAC model
    - scaler: Scaler used for feature scaling
    - poly: PolynomialFeatures object used for transformation
    """
    X = df[['grade_smooth']].values.reshape(-1, 1)
    y = df['velocity_smooth'].values

    # Create polynomial features
    poly = PolynomialFeatures(degree=degree)
    X_poly = poly.fit_transform(X)

    # Optional: Scale features for better performance
    scaler = StandardScaler()
    X_poly_scaled = scaler.fit_transform(X_poly)

    # Initialize RANSAC regressor with a polynomial estimator
    ransac = RANSACRegressor(
        estimator=LinearRegression(),
        min_samples=0.8,  # Minimum 80% of data for a good fit
        residual_threshold=2.0,  # Adjust based on data distribution
        random_state=42
    )

    ransac.fit(X_poly_scaled, y)

    inlier_mask = ransac.inlier_mask_
    outlier_mask = ~inlier_mask

    return inlier_mask, outlier_mask, ransac, scaler, poly

def visualize_trend(df, inlier_mask, outlier_mask, model, scaler, poly):
    """
    Plot the trend with inliers and outliers.
    """
    plt.figure(figsize=(12, 8))

    # Plot inliers
    plt.scatter(df.loc[inlier_mask, 'grade_smooth'],
                df.loc[inlier_mask, 'velocity_smooth'],
                c='blue', s=10, alpha=0.3, label='Inliers')

    # Plot outliers
    plt.scatter(df.loc[outlier_mask, 'grade_smooth'],
                df.loc[outlier_mask, 'velocity_smooth'],
                c='red', s=20, alpha=0.6, label='Outliers')

    # Plot the RANSAC regression line
    X_plot = np.linspace(df['grade_smooth'].min(), df['grade_smooth'].max(), 100).reshape(-1, 1)
    X_plot_poly = poly.transform(X_plot)
    X_plot_poly_scaled = scaler.transform(X_plot_poly)
    y_plot = model.predict(X_plot_poly_scaled)
    plt.plot(X_plot, y_plot, color='green', linewidth=2, label='RANSAC Fit')

    plt.xlabel('Grade Smooth (%)')
    plt.ylabel('Average Speed (min/km)')
    plt.title('Pace vs Grade with Outliers Identified by RANSAC (Polynomial)')
    plt.legend()
    plt.show()

def main():
    # Filepath to the combined dataset
    filepath = 'combined_data.csv'

    # Load and preprocess the data
    df = load_data(filepath)

    # Fit robust regression to identify outliers
    inlier_mask, outlier_mask, model, scaler, poly = fit_robust_regression(df, degree=3)

    # Add outlier labels to the dataframe
    df['outlier'] = outlier_mask.astype(int) * -1 + inlier_mask.astype(int)
    # -1 for outliers, 1 for inliers

    # Save the labeled data
    df.to_csv('combined_data_with_trend_outliers.csv', index=False)
    print("Trend analysis completed. Results saved to 'combined_data_with_trend_outliers.csv'.")

    # Visualize the trend and outliers
    visualize_trend(df, inlier_mask, outlier_mask, model, scaler, poly)

if __name__ == '__main__':
    main()
