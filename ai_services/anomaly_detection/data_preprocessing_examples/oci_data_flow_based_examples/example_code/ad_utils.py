import json
import backoff

from argparse import ArgumentParser
from oci.ai_anomaly_detection import AnomalyDetectionClient
from oci.ai_anomaly_detection.models import CreateModelDetails, \
    ModelTrainingDetails, CreateDataAssetDetails, \
    DataSourceDetailsObjectStorage, WorkRequest
from requests.exceptions import ConnectionError, RequestException, Timeout
from requests.structures import CaseInsensitiveDict

from example_code.dataflow_utils import \
    get_authenticated_client, DEFAULT_PROFILE, DEFAULT_LOCATION, \
    DataflowSession

DEFAULT_TARGET_FAP = 0.01
DEFAULT_TRAINING_FRACTION = 0.7
OPC_REQUEST_ID_KEY = "opc-request-id"
OPC_WORK_REQUEST_ID_KEY = "opc-work-request-id"

WORK_REQUEST_SUCCESS_STATES = {WorkRequest.STATUS_SUCCEEDED}
WORK_REQUEST_NON_SUCCESS_STATES = {WorkRequest.STATUS_FAILED, WorkRequest.STATUS_CANCELED}
WORK_REQUEST_TERMINAL_STATES = WORK_REQUEST_SUCCESS_STATES | WORK_REQUEST_NON_SUCCESS_STATES


class AdUtils:
    def __init__(self, dataflow_session, profile_name=DEFAULT_PROFILE,
                 file_location=DEFAULT_LOCATION, service_endpoint=None):
        client_args = {
            'profile_name': profile_name,
            'file_location': file_location,
            'dataflow_session': dataflow_session
        }
        if service_endpoint:
            client_args['service_endpoint'] = service_endpoint
            print(f"Will override AnomalyDetectionClient's endpoint with {service_endpoint}.")

        self.ad_client = get_authenticated_client(
            client=AnomalyDetectionClient, **client_args)
        print("Successfully created AdUtils object to interact with Anomaly Detection Service!!!")

    def train(self, project_id, compartment_id, data_asset_detail,
              target_fap=DEFAULT_TARGET_FAP,
              training_fraction=DEFAULT_TRAINING_FRACTION):
        data_asset_id = self._create_data_asset_(
            project_id, compartment_id, data_asset_detail['namespace'],
            data_asset_detail['bucket'], data_asset_detail['object'])
        print(f"Create data asset with ocid [{data_asset_id}]!")

        return self._train_model_(project_id, compartment_id, data_asset_id, target_fap, training_fraction)

    def _create_data_asset_(self, project_id, compartment_id, namespace,
                            bucket, object_name):
        data_source_details = DataSourceDetailsObjectStorage(
            namespace=namespace, bucket_name=bucket, object_name=object_name)
        create_data_asset_details = CreateDataAssetDetails(
            compartment_id=compartment_id, project_id=project_id,
            data_source_details=data_source_details)

        data_asset_create_response = self.ad_client.create_data_asset(
            create_data_asset_details)
        print(f"Create data-asset request received "
              f"status [{data_asset_create_response.status}] "
              f"opc-request-id [{get_header_value(data_asset_create_response.headers, OPC_REQUEST_ID_KEY)}]")
        assert data_asset_create_response.status == 200, f"Error creating data-asset: {data_asset_create_response.text}"

        return data_asset_create_response.data.id

    @backoff.on_exception(backoff.expo, (RequestException, Timeout, ConnectionError, AssertionError))
    @backoff.on_predicate(backoff.constant, lambda status: status not in WORK_REQUEST_TERMINAL_STATES, interval=120)
    def _poll_work_request_(self, work_request_id):
        work_request = self.ad_client.get_work_request(work_request_id)

        print(f"Get work-request received "
              f"status [{work_request.status}] "
              f"opc-request-id [{get_header_value(work_request.headers, OPC_REQUEST_ID_KEY)}]")
        assert work_request.status == 200, f"Error getting work-request information: {work_request.text}"

        print(f"{work_request_id} is in {work_request.data.status} state")
        return work_request.data.status

    def _train_model_(self, project_id, compartment_id, data_asset_id,
                      target_fap, training_fraction):
        model_training_details = ModelTrainingDetails(
            target_fap=target_fap, training_fraction=training_fraction,
            data_asset_ids=[data_asset_id])
        create_model_details = CreateModelDetails(
            compartment_id=compartment_id, project_id=project_id,
            model_training_details=model_training_details)
        create_model_response = self.ad_client.create_model(
            create_model_details)
        print(f"Create model request received "
              f"status [{create_model_response.status}] "
              f"opc-request-id [{get_header_value(create_model_response.headers, OPC_REQUEST_ID_KEY)}]")
        assert create_model_response.status == 201, \
            f"Error creating model: {create_model_response.text}"

        model_id = create_model_response.data.id
        work_request_id = get_header_value(create_model_response.headers, OPC_WORK_REQUEST_ID_KEY)

        assert self._poll_work_request_(work_request_id) in WORK_REQUEST_SUCCESS_STATES, \
            f"Unable to train model [{model_id}]!"
        print(f"Successfully trained model [{model_id}!!!")
        return model_id


def get_header_value(headers: CaseInsensitiveDict, header_key: str):
    return headers.get(header_key, f"<NO-{header_key.upper()}>")


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument("--profile_name", required=False, type=str,
                        default=DEFAULT_PROFILE)
    parser.add_argument("--service_endpoint", required=False, type=str,
                        default=None)
    parser.add_argument("--project_id", required=True, type=str)
    parser.add_argument("--compartment_id", required=True, type=str)
    parser.add_argument("--target_fap", required=False,
                        type=lambda v: float(v), default=DEFAULT_TARGET_FAP)
    parser.add_argument("--training_fraction", required=False,
                        type=lambda v: float(v),
                        default=DEFAULT_TRAINING_FRACTION)
    parser.add_argument("--data_asset_detail", required=True, type=str)
    args = parser.parse_args()

    _dataflow_session = DataflowSession(app_name='AnomalyDetectionClient')
    ad_utils = AdUtils(_dataflow_session, profile_name=args.profile_name,
                       service_endpoint=args.service_endpoint)
    _data_asset_detail = json.loads(str(args.data_asset_detail))
    _model_id = ad_utils.train(
        project_id=args.project_id, compartment_id=args.compartment_id,
        data_asset_detail=_data_asset_detail)
    print(f"Successfully trained model [{_model_id}] using {_data_asset_detail}")
