import re
import random

from heapq import heappush, heappop
from collections import defaultdict
from dataclasses import dataclass
from src.writes import write_json
from .Neuron import Neuron
from .Rule import Rule


@dataclass
class System:
    name: str
    neurons: list[Neuron]

    def to_dict(self) -> dict[str, any]:
        return {
            "name": self.name,
            "neurons": [neuron.to_dict() for neuron in self.neurons],
        }

    def to_dict_xmp(self) -> dict[str, any]:
        id_to_label = {}
        label_to_id = {}

        for neuron in self.neurons:
            id_to_label[neuron.id] = neuron.label
            label_to_id[neuron.label] = neuron.id

        neuron_entries = []

        for neuron in self.neurons:
            k = neuron.label
            v = {
                "id": neuron.label,
                "position": {
                    "x": neuron.position[0],
                    "y": neuron.position[1],
                },
                "rules": " ".join(
                    list(map(lambda rule: rule.form_rule_xmp(), neuron.rules))
                ),
                "startingSpikes": neuron.spikes,
                "delay": neuron.downtime,
                "spikes": neuron.spikes,
            }

            if neuron.is_input:
                v["isInput"] = True
                v["bitstring"] = Neuron.decompress_spike_times(neuron.spike_times)

            if neuron.is_output:
                v["isOutput"] = True
                v["bitstring"] = Neuron.decompress_spike_times(neuron.spike_times)

            for synapse in neuron.synapses:
                if "out" not in v:
                    v["out"] = []
                if "outWeights" not in v:
                    v["outWeights"] = {}
                v["out"].append(id_to_label[synapse.to])
                v["outWeights"][id_to_label[synapse.to]] = synapse.weight

            neuron_entries.append((k, v))

        return {"content": dict(neuron_entries)}

    def log(self, time: int):
        dict_new = self.to_dict()
        write_json(dict_new, f"{self.name}@{str(time).zfill(3)}", True)

    def simulate(self) -> bool:
        to_index = defaultdict(int)
        current_index = 0

        for neuron in self.neurons:
            if neuron.id not in to_index:
                to_index[neuron.id] = current_index
                current_index += 1

        incoming_spikes = [[] for _ in range(current_index)]  # @start of timestep

        time = 0
        done = False

        for neuron in self.neurons:
            if neuron.is_input:
                for t in neuron.spike_times:
                    heappush(incoming_spikes[to_index[neuron.id]], (t, 1))

        while not done and time < 10**3:
            for neuron in self.neurons:
                heap = incoming_spikes[to_index[neuron.id]]
                if neuron.downtime == 0:
                    while len(heap) > 0 and heap[0][0] == time:
                        neuron.spikes += heap[0][1]
                        heappop(heap)
                neuron.downtime = max(neuron.downtime - 1, 0)

            self.log(time)

            for neuron in self.neurons:
                if neuron.downtime == 0:
                    possible_indices = []

                    for index, rule in enumerate(neuron.rules):
                        python_regex = Rule.json_to_python_regex(rule.regex)
                        result = re.match(python_regex, "a" * neuron.spikes)
                        if result:
                            possible_indices.append(index)

                    if len(possible_indices) > 0:
                        chosen_index = random.choice(possible_indices)
                        rule = neuron.rules[chosen_index]
                        neuron.spikes -= rule.consumed
                        for synapse in neuron.synapses:
                            to, weight = synapse.to, synapse.weight
                            heappush(
                                incoming_spikes[to_index[to]],
                                (time + rule.delay + 1, rule.produced * weight),
                            )
                        if neuron.is_output:
                            neuron.spike_times.append(time + rule.delay)
                        neuron.downtime = rule.delay

            done = all([len(heap) == 0 for heap in incoming_spikes])
            time += 1
