from agency_swarm.tools import BaseTool
from pydantic import Field
import logging
import time

# Configure logging
logging.basicConfig(filename='error_log.txt', level=logging.ERROR, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

class ErrorHandling(BaseTool):
    """
    This tool handles exceptions and errors during the monitoring and processing of emails.
    It logs errors and attempts to recover from them to ensure continuous operation.
    """

    error_message: str = Field(
        ..., description="The error message or exception details to be logged and handled."
    )
    retry_attempts: int = Field(
        3, description="The number of retry attempts for recovering from an error."
    )
    retry_delay: int = Field(
        5, description="The delay in seconds between retry attempts."
    )

    def log_error(self):
        """
        Log the error message to a file.
        """
        try:
            logging.error(self.error_message)
            print(f"Error logged: {self.error_message}")
        except Exception as e:
            print(f"Failed to log error: {e}")

    def retry_operation(self, operation, *args, **kwargs):
        """
        Attempt to retry a failed operation.
        """
        attempt = 0
        while attempt < self.retry_attempts:
            try:
                result = operation(*args, **kwargs)
                return result
            except Exception as e:
                attempt += 1
                self.error_message = f"Retry attempt {attempt} failed: {e}"
                self.log_error()
                time.sleep(self.retry_delay)
        return None

    def run(self):
        """
        Handle the error by logging it and attempting to recover.
        """
        self.log_error()
        # Example usage of retry_operation
        # result = self.retry_operation(some_function, arg1, arg2)
        # if result is None:
        #     print("Failed to recover from error after retries.")
        return "Error handling completed."