from pyspark.sql import SparkSession
from pyspark.sql import functions as F
import argparse

ISO_TIMESTAMP_FORMAT = "yyyy-MM-dd'T'HH:mm:ss'Z'"

def __create_spark_session(session_name):
    """
    Create a Spark session
    Args:
        session_name: name to be assigned to the spark session
    Return:
        a spark session
    """
    spark_session = SparkSession.builder.appName(session_name).getOrCreate()
    return spark_session


# The empty **kwargs is for generalization of the function interface
def format_timestamp(df,
    columnName="timestamp",
    timestampFormat=ISO_TIMESTAMP_FORMAT, **kwargs):
    """
    Reformat timestamps to ISO 8601
    Args:
        df: input dataframe
        columnName: timestamp column name
        timestampFormat: timestamp format used

    Return:
        input dataframe with timestamps formatted as ISO 8601
    """
    return df.withColumn(
        columnName,
        F.date_format(
            F.to_timestamp(columnName, timestampFormat), ISO_TIMESTAMP_FORMAT
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--columnName", required=False, default="timestamp"
    )
    parser.add_argument(
        "--timestampFormat", required=False, default=ISO_TIMESTAMP_FORMAT
    )
    parser.add_argument("--coalesce", required=False, action="store_true")
    args = parser.parse_args()

    spark = __create_spark_session("pyspark_timestamp_formatting")
    input_data = spark.read.csv(
        args.input,
        sep=",",
        inferSchema=False,
        header=True)

    df = format_timestamp(input_data, **vars(args))

    if args.coalesce:
        df.coalesce(1).write.csv(args.output, header=True)
    else:
        df.write.csv(args.output, header=True)
