from celery import Celery

celeryapp = Celery('ei_mass_send', broker='amqp://localhost', backend='rpc://')
CHUNK_SIZE = 10


def get_batch_chunks(items, chunk_size):
    if len(items) <= chunk_size:
        return [items]
    last_chunk_size = len(items) % chunk_size
    last_chunk = tuple(items[(-last_chunk_size):])
    last_chunk_append = [last_chunk] if last_chunk_size != 0 else []
    chunk_list = zip(*[iter(items)] * chunk_size) + last_chunk_append
    return chunk_list


def batch_process(to_process_list, cursor_info, task=None):
    if not to_process_list:
        return
    batches = get_batch_chunks(to_process_list, CHUNK_SIZE)
    if task == 'send_invoice_batch':
        tasks = [
            celeryapp.send_task('tasks.send_invoice_batch',
                                (batch, cursor_info))
            for batch in batches
        ]
    elif task == 'read_xml_batch':
        tasks = [
            celeryapp.send_task('tasks.read_xml_batch', (batch, cursor_info))
            for batch in batches
        ]
    else:
        return
    while(filter(lambda task: task.status == 'PENDING', tasks)):
        pass
    return
