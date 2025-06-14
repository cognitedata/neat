import queue
import threading
from collections.abc import Callable, Iterable, Sized
from typing import Generic, TypeVar

from rich.console import Console
from rich.progress import BarColumn, Progress, TaskID, TaskProgressColumn, TextColumn, TimeRemainingColumn

T_Produced = TypeVar("T_Produced", bound=Sized)
T_Processed = TypeVar("T_Processed", bound=Sized)


class ProducerWorkerExecutor(Generic[T_Produced, T_Processed]):
    def __init__(
        self,
        producer_iterable: Iterable[T_Produced],
        work: Callable[[T_Processed], None],
        iteration_count: int,
        max_queue_size: int,
        process: Callable[[T_Produced], T_Processed] | None = None,
        produce_process_display_name: str = "Downloading...",
        work_process_display_name: str = "Writing to file...",
    ) -> None:
        self._producer_iterable = producer_iterable
        self.production_complete = False
        self.is_processing = False
        self._work = work
        self._process = process
        self.console = Console()
        self.process_queue: queue.Queue[T_Produced] = queue.Queue(maxsize=max_queue_size)
        self.work_queue: queue.Queue[T_Processed] = queue.Queue(maxsize=max_queue_size)
        self._produce_process_display_name = produce_process_display_name
        self._work_process_display_name = work_process_display_name

        self.iteration_count = iteration_count
        self.total_items = 0
        self.error_occurred = False
        self.error_message = ""

    def run(self) -> None:
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.console,
        ) as progress:
            produce_task = progress.add_task(self._produce_process_display_name, total=self.iteration_count)
            produce_thread = threading.Thread(target=self._producer_worker, args=(progress, produce_task))
            work_task = progress.add_task(self._work_process_display_name, total=self.iteration_count)
            write_thread = threading.Thread(target=self._write_worker, args=(progress, work_task))

            process_thread: threading.Thread | None = None
            if self._process is not None:
                process_task = progress.add_task("Processing", total=self.iteration_count)
                process_thread = threading.Thread(target=self._process_worker, args=(progress, process_task))

            produce_thread.start()
            if process_thread is not None:
                process_thread.start()
            write_thread.start()

            # Wait for all threads to finish
            produce_thread.join()
            if process_thread is not None:
                process_thread.join()
            write_thread.join()

    def _producer_worker(self, progress: Progress, produce_task: TaskID) -> None:
        """Thread for producing data."""
        iterator = iter(self._producer_iterable)
        while not self.error_occurred:
            try:
                items = next(iterator)
                self.total_items += len(items)
                while not self.error_occurred:
                    try:
                        self.process_queue.put(items, timeout=0.5)
                        progress.update(produce_task, advance=1)
                        break  # Exit the loop once the item is successfully added
                    except queue.Full:
                        # Retry until the queue has space
                        continue
            except StopIteration:
                self.production_complete = True
                break
            except Exception as e:
                self.error_occurred = True
                self.error_message = str(e)
                self.console.print(
                    f"[red]Error[/red] occurred while {self._produce_process_display_name}: {self.error_message}"
                )
                break

    def _process_worker(self, progress: Progress, process_task: TaskID) -> None:
        """Worker thread for processing data."""
        if self._process is None:
            raise ValueError("Process function must be provided for processing data.")
        self.is_processing = True
        while (not self.production_complete or not self.process_queue.empty()) and not self.error_occurred:
            try:
                items = self.process_queue.get(timeout=0.5)
                processed_items = self._process(items)
                self.work_queue.put(processed_items)
                progress.update(process_task, advance=1)
                self.process_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.error_occurred = True
                self.error_message = str(e)
                self.console.print(f"[red]ErrorError[/red] occurred while processing: {self.error_message}")
                break
        self.is_processing = False

    def _write_worker(self, progress: Progress, write_task: TaskID) -> None:
        """Worker thread for writing data to file."""
        source_queue = self.process_queue if self._process is None else self.work_queue
        while (
            not self.production_complete
            or self.is_processing
            or not self.work_queue.empty()
            or not self.process_queue.empty()
        ) and not self.error_occurred:
            try:
                items = source_queue.get(timeout=0.5)
                # Assume T_Processed = T_Produced if no _process function is provided
                self._work(items)  # type: ignore[arg-type]
                progress.update(write_task, advance=1)
                source_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.error_occurred = True
                self.error_message = str(e)
                self.console.print(
                    f"[red]Error[/red] occurred while {self._work_process_display_name}: {self.error_message}"
                )
                break
