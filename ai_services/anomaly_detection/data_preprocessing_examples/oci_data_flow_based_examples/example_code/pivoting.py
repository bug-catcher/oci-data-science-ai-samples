from pyspark.sql import SparkSession
import argparse
import pandas as pd
import numpy as np
from pyspark.sql import functions as F


class ParseKwargs(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        values = values[0].split(" ") if len(values) == 1 else values
        if ":" not in values[0]:
            setattr(namespace, self.dest, values)
        else:
            setattr(namespace, self.dest, dict())
            for value in values:
                key, value = value.split(":")
                getattr(namespace, self.dest)[key] = value


def spark_pivoting(df, **kwargs):
    """
    Pivot Operation
    Args:
        df: data framework based on input csv
        groupby: dimensions to groupby into summary rows
        pivot: pivot column - rows of which to be converted into columns
        agg: a dictionary
            where key = <column name> and value = <aggregation function>
    """
    groupby = kwargs["groupby"]
    if isinstance(groupby, str):
        groupby = groupby.split()
    agg = kwargs["agg"]
    agg_ops = dict()
    distinct_column_values = kwargs.get('distinct_column_values', None)

    if isinstance(agg, str):
        agg = agg.split()
        for kv in agg:
            key, value = kv.split(":")
            agg_ops[key] = value

    distinct_column = df.select(kwargs['pivot']).distinct().collect()
    pivot_res = df.groupBy(groupby).pivot(
        kwargs['pivot'], distinct_column_values).agg(agg_ops)
    return distinct_column, pivot_res


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--pivot", required=True)
    parser.add_argument(
        "--groupby",
        nargs="*",
        required=True,
        action=ParseKwargs)
    parser.add_argument("--agg", nargs="*", required=True, action=ParseKwargs)
    parser.add_argument("--coalesce", required=False, action="store_true")
    args = parser.parse_args()

    spark = SparkSession.builder.appName("PySpark_pivoting").getOrCreate()
    spark.conf.set("spark.sql.pivotMaxValues", "1000000")

    df = spark.read.load(
        args.input, format="csv", sep=",", inferSchema="true", header="true"
    )

    if "timestamp" not in df.columns:
        raise ValueError("timestamp column not found!")

    _, df_pivot = spark_pivoting(df, **vars(args))

    if args.coalesce:
        df_pivot.coalesce(1).write.csv(args.output, header=True)
    else:
        df_pivot.write.csv(args.output, header=True)
