import os
import copy
import numpy as np
import torch

from base.network import BaseNetwork

class DQN:

    def __init__(self, config):

        self.action_size = config['action_size']
        self.device = config['device']
        self.bounds = config['bounds']

        self.model = BaseNetwork(**config).to(config['device'])
        self.target = copy.deepcopy(self.model)
        self.target.eval()

        self.optimizer = torch.optim.Adam(self.model.parameters(),
                                          config['lrate'],
                                          weight_decay=config['decay'])

    def get_weights(self):
        return (self.model.state_dict(), self.target.state_dict())

    def set_weights(self, weights):
        self.model.load_state_dict(weights[0])
        self.target.load_state_dict(weights[1])

    def load_checkpoint(self, checkpoint_dir):
        """Loads a model from a directory containing a checkpoint."""

        if not os.path.exists(checkpoint_dir):
            raise Exception('No checkpoint directory <%s>' % checkpoint_dir)

        weights = torch.load(checkpoint_dir + '/model.pt', self.device)
        self.model.load_state_dict(weights)
        self.update()

    def save_checkpoint(self, checkpoint_dir):
        """Saves a model to a directory containing a single checkpoint."""

        if not os.path.exists(checkpoint_dir):
            os.makedirs(checkpoint_dir)
        torch.save(self.model.state_dict(), checkpoint_dir + '/model.pt')

    @torch.no_grad()
    def sample_action(self, state, timestep, explore_prob):
        """Samples an action to perform in the environment."""

        if np.random.random() < explore_prob:
            return np.random.uniform(*self.bounds, size=(self.action_size,))

        return self.model.sample_action(state, timestep)

    def train(self, memory, gamma, batch_size, **kwargs):
        """Performs a single step of Q-Learning."""

        # Sample data from the memory buffer & put on GPU
        s0, act, r, s1, term, timestep = memory.sample(batch_size)

        s0 = torch.from_numpy(s0).to(self.device)
        act = torch.from_numpy(act).to(self.device)
        r = torch.from_numpy(r).to(self.device)
        s1 = torch.from_numpy(s1).to(self.device)
        term = torch.from_numpy(term).to(self.device)
        t0 = torch.from_numpy(timestep).to(self.device)
        t1 = torch.from_numpy(timestep + 1).to(self.device)

        # Train the models
        pred = self.model(s0, t0, act).view(-1)

        # We don't calculate a gradient for the target network; these
        # weights instead get updated by copying the prediction network
        # weights every few training iterations
        with torch.no_grad():
            target = r + (1. - term) * gamma * self.target(s1, t1).view(-1)

        loss = torch.pow(pred - target, 2).mean()

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 10.)
        self.optimizer.step()
        self.model.zero_grad()

        return loss.detach()

    def update(self):
        """Copy the network weights every few epochs."""

        self.target.load_state_dict(self.model.state_dict())
        self.target.eval()
