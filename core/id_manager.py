import os
import random


class RandomIDManager:
    """
    Random ID generator within a range,
    without repetition and with persistence by rank.
    """

    def __init__(self, start_id, end_id, used_ids_folder="data/"):
        self.start_id = start_id
        self.end_id = end_id
        self.used_ids_folder = used_ids_folder

        # Crate folder if not exist
        os.makedirs(self.used_ids_folder, exist_ok=True)

        # specific file by rank
        self.used_ids_file = os.path.join(
            self.used_ids_folder,
            f"used_ids_{self.start_id}_{self.end_id}.txt"
        )

        # Load used IDs from range file
        self.used_ids = self._load_used_ids()

        # Calculate total possible IDs
        self.total_ids = self.end_id - self.start_id + 1

    # Load used IDs from file
    def _load_used_ids(self):
        """Load IDs already used only for this range."""
        if not os.path.exists(self.used_ids_file):
            return set()

        with open(self.used_ids_file, "r", encoding="utf-8") as f:
            return set(int(line.strip()) for line in f if line.strip().isdigit())

    # Save used IDs into file
    def _save_used_id(self, id_num):
        with open(self.used_ids_file, "a", encoding="utf-8") as f:
            f.write(f"{id_num}\n")

    # Get random ID
    def get_random_id(self):
        if len(self.used_ids) >= self.total_ids:
            raise RuntimeError("There are no more IDs available in the range.")

        while True:
            id_num = random.randint(self.start_id, self.end_id)
            if id_num not in self.used_ids:
                self.used_ids.add(id_num)
                self._save_used_id(id_num)
                return id_num

    # Get IDs batch
    def get_batch(self, count=10):
        """
        Returns a batch of non-repeating random IDs.
        If the range is exhausted, return whatever is available.
        """
        if len(self.used_ids) >= self.total_ids:
            raise RuntimeError("There are no more IDs available in the range.")

        batch = []
        for _ in range(count):
            try:
                batch.append(self.get_random_id())
            except RuntimeError:
                break

        return batch
