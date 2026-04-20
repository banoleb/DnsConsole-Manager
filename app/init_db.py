import logging

from console import create_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('web-console-init')
app = create_app()
logger.info('Database initialized successfully')
