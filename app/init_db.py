from console import create_app
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('web-console-init')
app = create_app()
logger.info(f'Database initialized successfully')