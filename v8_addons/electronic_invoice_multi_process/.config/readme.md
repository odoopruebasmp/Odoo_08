- Install celery: sudo pip install celery

- Install rabbit-mq: sudo apt install rabbitmq-server

- Instal grequests: sudo pip install grequests

- Create pid and logging directories:
  - sudo mkdir /var/log/celery/ && sudo chmod -R 777 /var/log/celery/
  - sudo mkdir /var/run/celery/ && sudo chmod -R 777 /var/run/celery/

- Use celery.service and celery.conf to create systemd daemon and run it
  - celery.service at /etc/systemd/system/celery.service with perms 755, WorkingDirectory might change, it must point to electronic_invoice_multi_process folder
  - celery.conf at /etc/celery.conf with owner odoo and perms 755, CELERY_BIN (might change) check by running: which celery

- Reload daemons: sudo systemctl daemon-reload

- Start: sudo systemctl start celery

- Check: sudo systemctl status celery

- In odoo, enable ei_batch_process on the company, field is invisible.

More info at https://docs.celeryproject.org/en/stable/userguide/daemonizing.html#daemonizing
