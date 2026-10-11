import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


class EDA:

    def __init__(self):

        # Project Root Folder
        self.base_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

        # Dataset Path
        self.dataset_path = os.path.join(
            self.base_dir,
            "dataset",
            "placement_predict_50k_Dataset.xlsx"
        )

        # Graph Save Folder
        self.graph_path = os.path.join(
            self.base_dir,
            "static",
            "graphs"
        )

        os.makedirs(
            self.graph_path,
            exist_ok=True
        )

        self.df = None

    # ==========================================
    # LOAD DATASET
    # ==========================================
    def load_dataset(self):

        print("=" * 60)
        print("LOADING DATASET")
        print("=" * 60)

        self.df = pd.read_excel(
            self.dataset_path,
            engine="openpyxl"
        )

        print("Dataset Loaded Successfully")
        print()

        return self.df

    # ==========================================
    # DATASET INFORMATION
    # ==========================================
    def dataset_information(self):

        print("=" * 60)
        print("DATASET INFORMATION")
        print("=" * 60)

        print("\nShape")
        print(self.df.shape)

        print("\nColumns")
        print(self.df.columns.tolist())

        print("\nData Types")
        print(self.df.dtypes)

        print("\nFirst 5 Rows")
        print(self.df.head())

        print("\nLast 5 Rows")
        print(self.df.tail())

        print("\nMissing Values")
        print(self.df.isnull().sum())

        print("\nDuplicate Rows")
        print(self.df.duplicated().sum())

        print("\nStatistics")
        print(self.df.describe(include="all"))

    # ==========================================
    # HISTOGRAM
    # ==========================================
    def histogram(self):

        print("\nGenerating Histograms...")

        numerical_columns = self.df.select_dtypes(
            include=["int64", "float64"]
        ).columns

        for column in numerical_columns:
            plt.figure(figsize=(8, 5))

            sns.histplot(
                data=self.df,
                x=column,
                kde=True,
                color="royalblue"
            )

            plt.title(f"Histogram - {column}")
            plt.xlabel(column)
            plt.ylabel("Frequency")
            plt.tight_layout()

            plt.savefig(
                os.path.join(
                    self.graph_path,
                    f"{column}_histogram.png"
                )
            )

            plt.close()

        print("Histograms Generated Successfully")

    # ==========================================
    # BOX PLOT
    # ==========================================
    def boxplot(self):

        print("\nGenerating Box Plots...")

        numerical_columns = self.df.select_dtypes(
            include=["int64", "float64"]
        ).columns

        for column in numerical_columns:
            plt.figure(figsize=(8, 5))

            sns.boxplot(
                y=self.df[column],
                color="orange"
            )

            plt.title(f"Box Plot - {column}")
            plt.ylabel(column)
            plt.tight_layout()

            plt.savefig(
                os.path.join(
                    self.graph_path,
                    f"{column}_boxplot.png"
                )
            )

            plt.close()

        print("Box Plots Generated Successfully")

    # ==========================================
    # COUNT PLOT
    # ==========================================
    def countplot(self):

        print("\nGenerating Count Plots...")

        categorical_columns = self.df.select_dtypes(
            include=["object", "category"]
        ).columns

        if len(categorical_columns) == 0:
            print("No categorical columns found.")
            return

        for column in categorical_columns:
            plt.figure(figsize=(8, 5))

            sns.countplot(
                data=self.df,
                x=column,
                palette="viridis",
                hue=column,  # Added hue to prevent Seaborn warning
                legend=False
            )

            plt.xticks(rotation=45)
            plt.title(f"Count Plot - {column}")
            plt.tight_layout()

            plt.savefig(
                os.path.join(
                    self.graph_path,
                    f"{column}_countplot.png"
                )
            )

            plt.close()

        print("Count Plots Generated Successfully")

    # ==========================================
    # SCATTER PLOT
    # ==========================================
    def scatterplot(self):

        print("\nGenerating Scatter Plot...")

        numerical_columns = self.df.select_dtypes(
            include=["int64", "float64"]
        ).columns

        if len(numerical_columns) < 2:
            print("Not enough numerical columns.")
            return

        x_column = numerical_columns[0]
        y_column = numerical_columns[1]

        plt.figure(figsize=(8, 5))

        sns.scatterplot(
            data=self.df,
            x=x_column,
            y=y_column,
            color="red"
        )

        plt.title(f"{x_column} vs {y_column}")
        plt.tight_layout()

        plt.savefig(
            os.path.join(
                self.graph_path,
                "scatter_plot.png"
            )
        )

        plt.close()

        print("Scatter Plot Generated Successfully")

    # ==========================================
    # CORRELATION HEATMAP
    # ==========================================
    def heatmap(self):

        print("\nGenerating Correlation Heatmap...")

        numerical_df = self.df.select_dtypes(
            include=["int64", "float64"]
        )

        plt.figure(figsize=(12, 8))

        sns.heatmap(
            numerical_df.corr(),
            annot=True,
            cmap="coolwarm",
            fmt=".2f"
        )

        plt.title("Correlation Heatmap")
        plt.tight_layout()

        plt.savefig(
            os.path.join(
                self.graph_path,
                "correlation_heatmap.png"
            )
        )

        plt.close()

        print("Correlation Heatmap Generated Successfully")

    # ==========================================
    # PAIR PLOT
    # ==========================================
    def pairplot(self):

        print("\nGenerating Pair Plot...")

        numerical_columns = self.df.select_dtypes(
            include=["int64", "float64"]
        ).columns

        # Limit to first 5 numerical columns
        if len(numerical_columns) > 5:
            numerical_columns = numerical_columns[:5]

        pair_df = self.df[numerical_columns]

        pair = sns.pairplot(pair_df)

        pair.fig.suptitle(
            "Pair Plot",
            y=1.02
        )

        pair.savefig(
            os.path.join(
                self.graph_path,
                "pairplot.png"
            )
        )

        plt.close("all")

        print("Pair Plot Generated Successfully")

    # ==========================================
    # RUN COMPLETE EDA
    # ==========================================
    def run(self):
        self.load_dataset()
        self.dataset_information()
        self.histogram()
        self.boxplot()
        self.countplot()
        self.scatterplot()
        self.heatmap()
        self.pairplot()

        print("\n" + "=" * 60)
        print("EDA COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print("Graphs saved in:")
        print(self.graph_path)
        print("=" * 60)


# ==========================================
# MAIN FUNCTION
# ==========================================
if __name__ == "__main__":
    eda = EDA()
    eda.run()