import dm10 
import numpy as np

class SparseDM:
    def __init__(self, names=None):
        """A given set of qubit is kept in a state 
        """
        if isinstance(names, int):
            names = list(range(names))

        self.names = names
        self.no_qubits = len(names)
        self.classical = {bit: 0 for bit in names}
        self.idx_in_full_dm = {}
        self.full_dm = dm10.Density(0)
        self.max_bits_in_full_dm = 0

        self.classical_probability = 1

        self.last_peak = None

    def ensure_dense(self, bit):
        """Make sure that the bit is removed from the classical bits and added to the
        density matrix, do nothing if it is already there."""
        if bit not in self.names:
            raise ValueError("This bit does not exist")
        if bit not in self.idx_in_full_dm:
            state = self.classical[bit]
            idx = self.full_dm.no_qubits
            self.full_dm = self.full_dm.add_ancilla(idx, state)
            del self.classical[bit]
            self.idx_in_full_dm[bit] = idx

            new_max = max(self.max_bits_in_full_dm, len(self.idx_in_full_dm))
            self.max_bits_in_full_dm = new_max

    def ensure_classical(self, bit, epsilon=1e-7):
        if bit not in self.names:
            raise ValueError("This bit does not exist")
        if bit in self.idx_in_full_dm:
            p0, p1 = self.peak_measurement(bit)
            if p0 < epsilon:
                self.project_measurement(bit, 1)
            elif p1 < epsilon:
                self.project_measurement(bit, 0)
            else:
                raise ValueError("Trying to classicalize entangled quantum bit")

    def peak_measurement(self, bit):
        """Calculate the two smaller density matrices that occur when 
        measuring qubit #bit. Return the probabilities. 

        The density matrices are stored and will be used by project_measurement
        if called with the same bit immediately afterwards
        """
        if bit in self.idx_in_full_dm:
            qbit = self.idx_in_full_dm[bit]
            p0, dm0, p1, dm1 = self.full_dm.measure_ancilla(qbit)
            self.last_peak = {'bit': bit, 0: dm0, 1: dm1}
            return (p0, p1)
        elif self.classical[bit] == 0:
            return (1, 0)
        elif self.classical[bit] == 1:
            return (0, 1)

    def project_measurement(self, bit, state): 
        """Project a bit to a fixed state, making it classical and 
        reducing the size of the full density matrix.
        The reduced density matrix is not normalized, so that
        its trace represents the probability for that event.
        """
        if bit in self.idx_in_full_dm:
            if self.last_peak == None or self.last_peak['bit'] != bit:
                self.peak_measurement(bit)
            self.full_dm = self.last_peak[state]
            self.classical[bit] = state
            for b in self.idx_in_full_dm:
                if self.idx_in_full_dm[b] > self.idx_in_full_dm[bit]:
                    self.idx_in_full_dm[b] -= 1
            del self.idx_in_full_dm[bit]
            self.last_peak = None
        else:
            raise ValueError("trying to measure classical bit")
    
    def peak_multiple_measurements(self, bits):
        """Obtain the probabilities for all combinations of a multiple
        qubit measurement. Act on a copy, do not destroy this density matrix.
        """
        classical_bits = {bit: self.classical[bit] for bit in bits if bit in self.classical}

        res = [(classical_bits, self.full_dm.copy())]

        bits = [bit for bit in bits if bit not in self.classical]

        bit_idxs = [(bit, self.idx_in_full_dm[bit]) for i,bit in enumerate(bits)]

        mask = 0
        for bit in bits:
            mask |= 1 << self.idx_in_full_dm[bit]

        diagonal = self.full_dm.get_diag()

        probs = {}

        for idx, prob in enumerate(diagonal):
            if idx & mask in probs:
                probs[idx & mask]  += prob
            else: 
                probs[idx & mask]  = prob

        res = []
        for idx in probs:
            outcome = classical_bits.copy()
            for bit in bits: 
                outcome[bit] = int(idx & (1 << self.idx_in_full_dm[bit])>0)

            res.append((outcome, probs[idx]))

        return res

    def trace(self):
        return self.classical_probability * self.full_dm.trace()

    def renormalize(self):
        self.full_dm.renormalize()
        self.classical_probability = 1

    def copy(self):
        """Return an identical but distinct copy of this object.

        If a measurement has been peaked at, the reduced density matrices are discarded.
        """

        cp = SparseDM(self.names)
        cp.classical = self.classical.copy()
        cp.idx_in_full_dm = self.idx_in_full_dm.copy()
        cp.last_peak = None
        cp.full_dm = self.full_dm.copy()

        return cp

    def cphase(self, bit0, bit1):
        """Apply a cphase gate between bit0 and bit1.
        """
        self.ensure_dense(bit0)
        self.ensure_dense(bit1)
        self.full_dm.cphase(self.idx_in_full_dm[bit0], 
                self.idx_in_full_dm[bit1])

    def hadamard(self, bit):
        """Apply a hadamard gate to qubit #bit.
        """
        self.ensure_dense(bit)
        self.full_dm.hadamard(self.idx_in_full_dm[bit])

    def amp_ph_damping(self, bit, gamma, lamda):
        """Apply amplitude and phase damping to qubit #bit.
        """
        self.ensure_dense(bit)
        self.full_dm.amp_ph_damping(self.idx_in_full_dm[bit], gamma, lamda)

    def rotate_y(self, bit, angle):
        self.ensure_dense(bit)
        c, s = np.cos(angle/2), np.sin(angle/2)
        self.full_dm.rotate_y(self.idx_in_full_dm[bit], c, s)


    def set_bit(self, bit, value):
        self.ensure_classical(bit)
        self.classical[bit] = value
