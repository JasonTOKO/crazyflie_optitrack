import osqp
import numpy as np
# import scipy as sp
import scipy.sparse as sparse
# from c2d import c2d


class mpc(object):

    def __init__(self, x0, xr, horizon):
        self.g = 9.8
        pi = 3.14
        '''
        # continuous system
        self.Ac = sparse.csc_matrix([
            [0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 1],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0]
        ])
        self.Bc = sparse.csc_matrix([
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
            [self.g, 0, 0],
            [0, -self.g, 0],
            [0, 0, 1.0/0.044]
        ])
        print("rank: ", np.rank(np.array(self.Ac)))
        self.Ad, self.Bd = c2d(np.array(self.Ac), np.array(self.Bc), 0.02)
        '''
        # discretized system 50Hz
        self.Ad = sparse.csc_matrix([
            [1., 0., 0., 0.02, 0.,   0.],
            [0., 1., 0., 0.,   0.02, 0.],
            [0., 0., 1., 0.,   0.,   0.02],
            [0., 0., 0., 1.,   0.,   0.],
            [0., 0., 0., 0.,   1.,   0.],
            [0., 0., 0., 0.,   0.,   1.]
        ])
        self.Bd = sparse.csc_matrix([
            [0.002, 0.,    0.],
            [0.,   -0.002, 0.],
            [0.,    0.,    0.0045],
            [0.196, 0.,    0.],
            [0.,   -0.196, 0.],
            [0.,    0.,    0.4545]
        ])

        self.nx = self.Bd.shape[0]
        self.nu = self.Bd.shape[1]

        u0 = np.array([0., 0., 0])
        # roll, pitch, thrust
        # self.umin = np.array([-pi/8., -pi/8.,-0.75]) - u0  # -0.75N when equivalent, not 0
        # self.umax = np.array([ pi/8.,  pi/8., 0.75]) - u0
        self.umin = np.array([-pi/8., -pi/8.,-0.75]) - u0  # -0.75N when equivalent, not 0
        self.umax = np.array([ pi/8.,  pi/8., 0.75]) - u0

        self.xmin = np.array([-np.inf, -np.inf, -np.inf, -np.inf, -np.inf, -np.inf])
        self.xmax = np.array([ np.inf,  np.inf,  np.inf,  np.inf,  np.inf,  np.inf])
        # self.xmin = np.array([-0.5, -np.inf, -np.inf, -np.inf, -np.inf, -np.inf])
        # self.xmax = np.array([0.5, np.inf, np.inf, np.inf, np.inf, np.inf])


        self.Q = sparse.diags([8., 6., 8., 1., 1., 2.])
        self.QN = sparse.diags([10., 10., 10., 2., 2., 4.])
        # self.Q = sparse.diags([0.8, 0.8, 1., 0.2, 0.2, 0.4])
        # self.QN = sparse.diags([1., 1., 1., 0.5, 0.5, 0.5])
        self.R = sparse.diags([6., 6., 8.])

        self.x0 = np.array(x0)
        self.xr = np.array(xr)

        self.N = horizon

    def solve(self):
        # Cast MPC problem to a QP: x = (x(0),x(1),...,x(N),u(0),...,u(N-1))

        # - quadratic objective
        P = sparse.block_diag([sparse.kron(sparse.eye(self.N), self.Q), self.QN,
                               sparse.kron(sparse.eye(self.N), self.R)]).tocsc()
        q = np.hstack([np.kron(np.ones(self.N), -self.Q.dot(self.xr)), -self.QN.dot(self.xr),
                       np.zeros(self.N * self.nu)])

        # - linear dynamics
        Ax = sparse.kron(sparse.eye(self.N + 1), -sparse.eye(self.nx)) + sparse.kron(sparse.eye(self.N + 1, k=-1), self.Ad)
        Bu = sparse.kron(sparse.vstack([sparse.csc_matrix((1, self.N)), sparse.eye(self.N)]), self.Bd)
        Aeq = sparse.hstack([Ax, Bu])
        leq = np.hstack([-self.x0, np.zeros(self.N * self.nx)])
        ueq = leq

        # - input and state constraints
        Aineq = sparse.eye((self.N + 1) * self.nx + self.N * self.nu)
        lineq = np.hstack([np.kron(np.ones(self.N + 1), self.xmin), np.kron(np.ones(self.N), self.umin)])
        uineq = np.hstack([np.kron(np.ones(self.N + 1), self.xmax), np.kron(np.ones(self.N), self.umax)])

        # - OSQP constraints
        A = sparse.vstack([Aeq, Aineq]).tocsc()
        l = np.hstack([leq, lineq])
        u = np.hstack([ueq, uineq])

        # Create an OSQP object
        prob = osqp.OSQP()

        # Setup workspace
        prob.setup(P, q, A, l, u, warm_start=True)

        # Solve
        res = prob.solve()

        # Check solver status
        if res.info.status != 'solved':
            raise ValueError('OSQP did not solve the problem!')

        # Apply first control input to the plant
        ctrl = res.x[-self.N * self.nu:-(self.N - 1) * self.nu]
        print("ctrl: ", ctrl)

        return ctrl

