from abc import abstractmethod
from io import StringIO
from pyspark.sql import functions as F

import oci
import pandas as pd

from example_code.dataflow_utils import get_authenticated_client, DataflowSession, get_spark_context


class ContentDeliveryFactory:
    """
    ContentDeliveryFactory returns database specific helper and contains common methods for the helpers.
    """

    def __init__(self, dataflow_session: DataflowSession):
        self.dataflow_session = dataflow_session

    @staticmethod
    def get(source, dataflow_session: DataflowSession):
        if source == ObjectStorageHelper.SOURCE:
            return ObjectStorageHelper(dataflow_session)
        raise NotImplementedError(f"{source} is not supported!")

    @abstractmethod
    def get_df(self, event_data: dict):
        pass

    def to_df(self, raw_content: str):
        data = StringIO(raw_content)
        pd_df = pd.read_csv(data, sep=",")

        spark_context = get_spark_context(dataflow_session=self.dataflow_session)
        df = spark_context.createDataFrame(pd_df)
        return df.select([F.col(x).alias(x.lower()) for x in df.columns])


class ObjectStorageHelper(ContentDeliveryFactory):
    """
    ObjectStorageHelper is an Object-Storage specific helper that contains methods for getting and putting objects.
    """
    SOURCE = "ObjectStorage"

    def __init__(self, dataflow_session: DataflowSession):
        super().__init__(dataflow_session)
        self.object_storage_client = get_authenticated_client(oci.object_storage.ObjectStorageClient,
                                                              dataflow_session=dataflow_session)

    def get_df(self, event_data: dict):
        if 'eventType' in event_data:
            namespace = event_data['data']['additionalDetails']['namespace']
            bucket = event_data['data']['additionalDetails']['bucketName']
            object_name = event_data['data']['resourceName']
        else:
            namespace = event_data['namespace']
            bucket = event_data['bucket']
            object_name = event_data['object']

        get_resp = self.object_storage_client.get_object(namespace, bucket, object_name)
        assert get_resp.status in [
            200,
            304,
        ], f"Unable to get content from /n/{namespace}/b/{bucket}/o/{object_name}! Response: {get_resp.text}"
        return self.to_df(get_resp.data.text)
