import logging
import json
import os
import azure.functions as func
from fhir_data_generation.fhir_resource_generation import fhir_resource_generation_blueprint, generate_fhir_bundle
from fhir_data_validation.fhir_resource_validation import fhir_resource_validation_blueprint, validate_fhir_data


app = func.FunctionApp()
app.register_blueprint(fhir_resource_generation_blueprint)
app.register_blueprint(fhir_resource_validation_blueprint)


@app.function_name(name="FHIRResourceGenerationAPI")  
@app.route(route="FHIRResourceGenerationAPI", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)  
def fhir_resource_generation(req: func.HttpRequest) -> func.HttpResponse:  
    logging.info('Processing request to generate FHIR bundles.')
  
    try:
        # Parse user-provided parameters
        user_parameters = req.get_json()

        return generate_fhir_bundle(user_parameters)
    except ValueError as e:  
        logging.error(f"Error parsing user parameters: {e}")  
        return func.HttpResponse(  
            "Invalid JSON data provided in the request body.",  
            status_code=400  
        )  
    except Exception as e:  
        logging.error(f"Unexpected error: {e}")  
        return func.HttpResponse(  
            "An unexpected error occurred while processing the request.",  
            status_code=500  
        )
    

@app.function_name(name="FHIRBundleValidationAPI")  
@app.route(route="FHIRBundleValidationAPI", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)  
def fhir_resource_validation(req: func.HttpRequest) -> func.HttpResponse:  
    logging.info('Processing request to validate FHIR bundle.')  
  
    try:  
        # Try to get JSON body from the request  
        try:  
            req_body = req.get_json()  
        except ValueError:  
            logging.error("file_path parameter is missing.")  
            return func.HttpResponse(  
                json.dumps({  
                    "status": "error",  
                    "message": "file_path parameter is required."  
                }),  
                status_code=400,  
                mimetype="application/json"  
            )
        
        # Extract the filename from the request body
        file_path = req_body.get('file_path')  

        # Check if the file path parameter is provided
        if not file_path:  
            logging.error("file_path parameter is empty.")
            return func.HttpResponse(  
                json.dumps({
                    "status": "error", 
                    "message": "file_path parameter cannot be empty."
                }),  
                status_code=400,  
                mimetype="application/json"  
            )
        
        # Check if the given file actually exists  
        if not os.path.isfile(file_path):
            logging.error("Provided FHIR bundle file does not exist.")
            return func.HttpResponse(  
                json.dumps({
                    "status": "error",  
                    "message": f"Provided FHIR bundle file does not exist."  
                }),  
                status_code=400,  
                mimetype="application/json"  
            )

        # Call the validate_fhir_data function to validate the FHIR data
        return validate_fhir_data(file_path)
    except Exception as e:  
        logging.error(f"Exception during validation request: {e}")  
        return func.HttpResponse(  
            json.dumps({
                "status": "error", 
                "message": "An error occurred while processing the validation request."
            }),  
            status_code=500,  
            mimetype="application/json"  
        )