from sklearn.base import BaseEstimator, TransformerMixin
import networkx as nx
import subprocess as sp
import os
import numpy as np

import logging
logger = logging.getLogger(__name__)


def sequence_dotbracket_to_graph(seq_info=None, seq_struct=None):
    """
    Parameters
    ----------
    seq_info : string
        node labels eg a sequence string

    seq_struct : string
        dotbracket string

    Returns
    -------
    A nx.Graph secondary struct associated with seq_struct
    """

    graph = nx.Graph()
    lifo = list()
    for i, (c, b) in enumerate(zip(seq_info, seq_struct)):
        graph.add_node(i, label=c, position=i)
        if i > 0:
            graph.add_edge(i, i - 1, label='-', type='backbone', len=1)
        if b == '(':
            lifo.append(i)
        if b == ')':
            j = lifo.pop()
            graph.add_edge(i, j, label='=', type='basepair', len=1)
    return graph

# ----------------------------------------------------------------------------------------------


class PathGraphToRNAFold(BaseEstimator, TransformerMixin):

    """
    Transform path graph of RNA sequence into structure graph according to RNAfold.

    """

    def __init__(self):
        pass

    def fit(self):
        return self

    def transform(self, graphs):
        '''
        Parameters
        ----------
        graphs : iterator over path graphs of RNA sequences


        Returns
        -------
        Iterator over networkx graphs.
        '''
        try:
            for graph in graphs:
                yield self.string_to_networkx(graph.graph['header'], graph.graph['sequence'])
        except Exception as e:
            logger.debug('Failed iteration. Reason: %s' % e)
            logger.debug('Exception', exc_info=True)

    def rnafold_wrapper(self, sequence):
        # defaults
        flags = '--noPS'
        # command line
        cmd = 'echo "%s" | RNAfold %s' % (sequence, flags)
        out = sp.check_output(cmd, shell=True)
        text = out.strip().split('\n')
        seq_info = text[0]
        seq_struct = text[1].split()[0]
        return seq_info, seq_struct

    def string_to_networkx(self, header, sequence, **options):
        seq_info, seq_struct = self.rnafold_wrapper(sequence, **options)
        graph = sequence_dotbracket_to_graph(seq_info=seq_info, seq_struct=seq_struct)
        graph.graph['info'] = header
        graph.graph['sequence'] = sequence
        graph.graph['structure'] = seq_struct
        graph.graph['header'] = header
        return graph


# ----------------------------------------------------------------------------------------------

class PathGraphToRNAShapes(BaseEstimator, TransformerMixin):

    """
    Transform path graph of RNA sequence into structure graph according to
    the RNAShapes algorithm.

    Parameters
    ----------

    shape_type : int (default 5)
        Is the level of abstraction or dissimilarity which defines a different shape.
        In general, helical regions are depicted by a pair of opening and closing brackets
        and unpaired regions are represented as a single underscore. The differences of the
        shape types are due to whether a structural element (bulge loop, internal loop, multiloop,
        hairpin loop, stacking region and external loop) contributes to the shape representation:
        Five types are implemented.
        1   Most accurate - all loops and all unpaired  [_[_[]]_[_[]_]]_
        2   Nesting pattern for all loop types and unpaired regions in external loop
        and multiloop [[_[]][_[]_]]
        3   Nesting pattern for all loop types but no unpaired regions [[[]][[]]]
        4   Helix nesting pattern in external loop and multiloop [[][[]]]
        5   Most abstract - helix nesting pattern and no unpaired regions [[][]]

    energy_range : float (default 10)
        Sets the energy range as percentage value of the minimum free energy.
        For example, when relative deviation is specified as 5.0, and the minimum free energy
        is -10.0 kcal/mol, the energy range is set to -9.5 to -10.0 kcal/mol.
        Relative deviation must be a positive floating point number; by default it is set to to 10 %.

    max_num : int (default 3)
        Is the maximum number of structures that are generated.

    split_components : bool (default False)
        If True each structure is yielded as an independent graph. Otherwise all structures
        are part of the same graph that has therefore several disconnectd components.
    """

    def __init__(self, shape_type=5, energy_range=10, max_num=3, split_components=False):
        self.shape_type = shape_type
        self.energy_range = energy_range
        self.max_num = max_num
        self.split_components = split_components

    def fit(self):
        return self

    def transform(self, graphs):
        '''
        Parameters
        ----------
        graphs : iterator over path graphs of RNA sequences


        Returns
        -------
        Iterator over networkx graphs.
        '''
        try:
            for graph in graphs:
                structures = self.string_to_networkx(graph.graph['header'], graph.graph['sequence'])
                for structure in structures:
                    yield structure
        except Exception as e:
            logger.debug('Failed iteration. Reason: %s' % e)
            logger.debug('Exception', exc_info=True)

    def string_to_networkx(self, header, sequence):
        seq_info, seq_struct_list, struct_list = self.rnashapes_wrapper(sequence,
                                                                        shape_type=self.shape_type,
                                                                        energy_range=self.energy_range,
                                                                        max_num=self.max_num)
        if self.split_components:
            for seq_struct, struct in zip(seq_struct_list, struct_list):
                graph = sequence_dotbracket_to_graph(seq_info=seq_info, seq_struct=seq_struct)
                graph.graph['info'] = 'RNAshapes shape_type=%s energy_range=%s max_num=%s' % (
                    self.shape_type,
                    self.energy_range,
                    self.max_num)
                graph.graph['id'] = header + '_' + struct
                graph.graph['sequence'] = sequence
                graph.graph['structure'] = seq_struct
                yield graph
        else:
            graph_global = nx.Graph()
            graph_global.graph['id'] = header
            graph_global.graph['info'] = 'RNAshapes shape_type=%s energy_range=%s max_num=%s' % (
                self.shape_type,
                self.energy_range,
                self.max_num)
            graph_global.graph['sequence'] = sequence
            for seq_struct in seq_struct_list:
                graph = sequence_dotbracket_to_graph(seq_info=seq_info, seq_struct=seq_struct)
                graph_global = nx.disjoint_union(graph_global, graph)
            yield graph_global

    def rnashapes_wrapper(self, sequence, shape_type=None, energy_range=None, max_num=None):
        # command line
        cmd = 'echo "%s" | RNAshapes -t %d -c %d -# %d' % (sequence, shape_type, energy_range, max_num)
        out = sp.check_output(cmd, shell=True)
        # parse output
        text = out.strip().split('\n')
        seq_info = text[0]
        if 'configured to print' in text[-1]:
            struct_text = text[1:-1]
        else:
            struct_text = text[1:]
        seq_struct_list = [line.split()[1] for line in struct_text]
        struct_list = [line.split()[2] for line in struct_text]
        return seq_info, seq_struct_list, struct_list


# ----------------------------------------------------------------------------------------------

class PathGraphToRNAPlfold(BaseEstimator, TransformerMixin):

    """
    Transform path graph of RNA sequence into structure graph according to
    the RNAPlfold algorithm.

    Parameters
    ----------
    max_num_edges : int (default 1)
        Is the maximal number of base pair bonds allowed per nucleotide.

    window_size : int (default 150)
        Is the size of the window.

    max_bp_span : int (default 100)
        Is the maximum number of bases between to bases that pair.

    avg_bp_prob_cutoff : float (default 0.2)
        Is the threshold value under which the edge is not materialized.

    no_lonely_bps : bool (default True)
        If True no lonely base pairs are allowed.

    nesting : bool (default False)
        If True the edge type is 'nesting'
    """

    def __init__(self, max_num_edges=1, window_size=150, max_bp_span=100,
                 avg_bp_prob_cutoff=0.2, no_lonely_bps=True, nesting=False):
        self.max_num_edges = max_num_edges
        self.window_size = window_size
        self.max_bp_span = max_bp_span
        self.avg_bp_prob_cutoff = avg_bp_prob_cutoff
        self.no_lonely_bps = no_lonely_bps
        self.nesting = nesting

    def fit(self):
        return self

    def transform(self, graphs):
        '''
        Parameters
        ----------
        graphs : iterator over path graphs of RNA sequences


        Returns
        -------
        Iterator over networkx graphs.
        '''
        try:
            for graph in graphs:
                yield self.string_to_networkx(graph.graph['header'], graph.graph['sequence'])
        except Exception as e:
            logger.debug('Failed iteration. Reason: %s' % e)
            logger.debug('Exception', exc_info=True)

    def rnaplfold_wrapper(self,
                          sequence,
                          max_num_edges=None,
                          window_size=None,
                          max_bp_span=None,
                          avg_bp_prob_cutoff=None,
                          no_lonely_bps=None):
        no_lonely_bps_str = ""
        if no_lonely_bps:
            no_lonely_bps_str = "--noLP"
        # Call RNAplfold on command line.
        cmd = 'echo "%s" | RNAplfold -W %d -L %d -c %.2f %s' % (sequence,
                                                                window_size,
                                                                max_bp_span,
                                                                avg_bp_prob_cutoff,
                                                                no_lonely_bps_str)
        sp.check_output(cmd, shell=True)
        # Extract base pair information.
        start_flag = False
        plfold_bp_list = []
        with open('plfold_dp.ps') as f:
            for line in f:
                if start_flag:
                    values = line.split()
                    if len(values) == 4:
                        avg_prob = values[2]
                        source_id = values[0]
                        dest_id = values[1]
                        plfold_bp_list.append((avg_prob, source_id, dest_id))
                if 'start of base pair probability data' in line:
                    start_flag = True
        # Delete RNAplfold output file.
        os.remove("plfold_dp.ps")
        # Return list with base pair information.
        return plfold_bp_list

    def string_to_networkx(self, header, sequence, **options):
        # Sort edges by average base pair probability in order to stop after
        # max_num_edges edges have been added to a specific vertex.
        max_num_edges = options.get('max_num_edges', 1)
        window_size = options.get('window_size', 150)
        max_bp_span = options.get('max_bp_span', 100)
        avg_bp_prob_cutoff = options.get('avg_bp_prob_cutoff', 0.2)
        no_lonely_bps = options.get('no_lonely_bps', True)
        nesting = options.get('nesting', False)

        plfold_bp_list = sorted(self.rnaplfold_wrapper(sequence,
                                                       max_num_edges=max_num_edges,
                                                       window_size=window_size,
                                                       max_bp_span=max_bp_span,
                                                       avg_bp_prob_cutoff=avg_bp_prob_cutoff,
                                                       no_lonely_bps=no_lonely_bps), reverse=True)
        graph = nx.Graph()
        graph.graph['id'] = header
        graph.graph['info'] = \
            'RNAplfold: max_num_edges=%s window_size=%s max_bp_span=%s avg_bp_prob_cutoff=%s no_lonely_bps=%s'\
            % (max_num_edges, window_size, max_bp_span, avg_bp_prob_cutoff, no_lonely_bps)
        graph.graph['sequence'] = sequence
        # Add nucleotide vertices.
        for i, c in enumerate(sequence):
            graph.add_node(i, label=c, position=i)
        # Add plfold base pairs and average probabilites.
        for avg_prob_str, source_str, dest_str in plfold_bp_list:
            source = int(source_str) - 1
            dest = int(dest_str) - 1
            avg_prob = float(avg_prob_str) ** 2
            # Check if either source or dest already have more than max_num_edges edges.
            if len(graph.edges(source)) >= max_num_edges or len(graph.edges(dest)) >= max_num_edges:
                pass
            else:
                if nesting:
                    graph.add_edge(source, dest, label='=', type='basepair', nesting=True, weight=avg_prob)
                else:
                    graph.add_edge(source, dest, label='=', type='basepair', prob=avg_prob)
        # Add backbone edges.
        for i, c in enumerate(sequence):
            if i > 0:
                graph.add_edge(i, i - 1, label='-', type='backbone')
        return graph

# ----------------------------------------------------------------------------------------------


class PathGraphToRNASubopt(BaseEstimator, TransformerMixin):

    """
    Transform path graph of RNA sequence into structure graph according to
    the RNASubopt algorithm.

    Parameters
    ----------
    energy_range : float (default 10)
        Sets the energy range as percentage value of the minimum free energy.
        For example, when relative deviation is specified as 5.0, and the minimum free energy
        is -10.0 kcal/mol, the energy range is set to -9.5 to -10.0 kcal/mol.
        Relative deviation must be a positive floating point number; by default it is set to to 10 %.

    max_num : int (default 3)
        Is the maximum number of structures that are generated.

    max_num_subopts : int (default 100)
        Is the maximum number of structures that are generated by RNAsubopt.

    split_components : bool (default False)
        If True each structure is yielded as an independent graph. Otherwise all structures
        are part of the same graph that has therefore several disconnectd components.
    """

    def __init__(self, energy_range=10, max_num=3, max_num_subopts=100, split_components=False):
        self.energy_range = energy_range
        self.max_num = max_num
        self.max_num_subopts = max_num_subopts
        self.split_components = split_components

    def fit(self):
        return self

    def transform(self, graphs):
        '''
        Parameters
        ----------
        graphs : iterator over path graphs of RNA sequences


        Returns
        -------
        Iterator over networkx graphs.
        '''
        try:
            for graph in graphs:
                header = graph.graph['header']
                sequence = graph.graph['sequence']
                constraint = graph.graph.get('constraint', None)
                structures = self.string_to_networkx(header=header, sequence=sequence, constraint=constraint)
                for structure in structures:
                    yield structure
        except Exception as e:
            logger.debug('Failed iteration. Reason: %s' % e)
            logger.debug('Exception', exc_info=True)

    def difference(self, seq_a, seq_b):
        ''' Compute the number of characters that are different between the two sequences.'''

        return sum(1 if a != b else 0 for a, b in zip(seq_a, seq_b))

    def difference_matrix(self, seqs):
        ''' Compute the matrix of differences between all pairs of sequences in input.'''

        size = len(seqs)
        diff_matrix = np.zeros((size, size))
        for i in range(size):
            for j in range(i + 1, size):
                diff_matrix[i, j] = self.difference(seqs[i], seqs[j])
        return diff_matrix + diff_matrix.T

    def max_difference_subselection(self, seqs, scores=None, max_num=None):
        # extract difference matrix
        diff_matrix = self.difference_matrix(seqs)
        size = len(seqs)
        m = np.max(diff_matrix) + 1
        # iterate size - k times, i.e. until only k instances are left
        for t in range(size - max_num):
            # find pairs with smallest difference
            (min_i, min_j) = np.unravel_index(np.argmin(diff_matrix), diff_matrix.shape)
            # choose instance with highest score
            if scores[min_i] > scores[min_j]:
                id = min_i
            else:
                id = min_j
            # remove instance with highest score by setting all its pairwise differences to max value
            diff_matrix[id, :] = m
            diff_matrix[:, id] = m
        # extract surviving elements, i.e. element that have 0 on the diagonal
        return np.array([i for i, x in enumerate(np.diag(diff_matrix)) if x == 0])

    def rnasubopt_wrapper(self, sequence, constraint=None):
        # command line
        if constraint is None:
            cmd = 'echo "%s" | RNAsubopt -e %d' % (sequence, self.energy_range)
        else:
            cmd = 'echo "%s\n%s" | RNAsubopt -C -e %d' % (sequence, constraint, self.energy_range)
        out = sp.check_output(cmd, shell=True)
        # parse output
        text = out.strip().split('\n')
        seq_struct_list = [line.split()[0] for line in text[1:self.max_num_subopts]]
        energy_list = [line.split()[1] for line in text[1:self.max_num_subopts]]
        selected_ids = self.max_difference_subselection(seq_struct_list,
                                                        scores=energy_list,
                                                        max_num=self.max_num)
        np_seq_struct_list = np.array(seq_struct_list)
        selected_seq_struct_list = list(np_seq_struct_list[selected_ids])
        selected_energy_list = list(np.array(energy_list)[selected_ids])
        return selected_seq_struct_list, selected_energy_list

    def string_to_networkx(self, header=None, sequence=None, constraint=None):
        seq_struct_list, energy_list = self.rnasubopt_wrapper(sequence)
        if self.split_components:
            for seq_struct, energy in zip(seq_struct_list, energy_list):
                graph = sequence_dotbracket_to_graph(seq_info=sequence, seq_struct=seq_struct)
                graph.graph['info'] = 'RNAsubopt energy=%s max_num=%s' % (energy, self.max_num)
                graph.graph['id'] = header
                graph.graph['sequence'] = sequence
                graph.graph['structure'] = seq_struct
                yield graph
        else:
            graph_global = nx.Graph()
            graph_global.graph['id'] = header
            graph_global.graph['info'] = 'RNAsubopt energy_range=%s max_num=%s' % \
                (self.energy_range, self.max_num)
            graph_global.graph['sequence'] = sequence
            for seq_struct in seq_struct_list:
                graph = sequence_dotbracket_to_graph(seq_info=sequence, seq_struct=seq_struct)
                graph_global = nx.disjoint_union(graph_global, graph)
            yield graph_global
