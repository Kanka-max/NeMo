# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
# Copyright 2015 and onwards Google, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from nemo_text_processing.text_normalization.en.graph_utils import NEMO_ALPHA, NEMO_DIGIT, GraphFst, get_abs_path

try:
    import pynini
    from pynini.lib import pynutil

    PYNINI_AVAILABLE = True
except (ModuleNotFoundError, ImportError):
    PYNINI_AVAILABLE = False


class ElectronicFst(GraphFst):
    """
    Finite state transducer for classifying electronic: as URLs, email addresses, etc.
        e.g. cdf1@abc.edu -> tokens { electronic { username: "cdf1" domain: "abc.edu" } }

    Args:
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, deterministic: bool = True):
        super().__init__(name="electronic", kind="classify", deterministic=deterministic)

        accepted_symbols = []
        with open(get_abs_path("data/electronic/symbols.tsv"), 'r') as f:
            for line in f:
                symbol, _ = line.split('\t')
                accepted_symbols.append(pynini.accep(symbol))

        accepted_symbols = NEMO_ALPHA + pynini.closure(NEMO_ALPHA | NEMO_DIGIT | pynini.union(*accepted_symbols))
        graph_symbols = pynini.string_file(get_abs_path("data/electronic/symbols.tsv")).optimize()

        username = pynutil.insert("username: \"") + accepted_symbols + pynutil.insert("\"") + pynini.cross('@', ' ')
        domain_graph = accepted_symbols + pynini.accep('.') + accepted_symbols
        domain_graph = pynutil.insert("domain: \"") + domain_graph + pynutil.insert("\"")

        protocol_start = pynini.accep("https://") | pynini.accep("http://")
        protocol_symbols = pynini.closure(
            (NEMO_ALPHA | pynutil.add_weight(graph_symbols | pynini.cross(":", "colon"), -0.1)) + pynutil.insert(" ")
        )
        protocol_end = pynini.accep("www.")
        protocol = protocol_start | protocol_end | (protocol_start + protocol_end)
        protocol = pynini.compose(protocol, protocol_symbols)
        protocol = pynutil.insert("protocol: \"") + protocol + pynutil.insert("\"")
        graph = pynini.closure(username, 0, 1) + domain_graph
        graph |= protocol + pynutil.insert(" ") + domain_graph

        final_graph = self.add_tokens(graph)
        self.fst = final_graph.optimize()
