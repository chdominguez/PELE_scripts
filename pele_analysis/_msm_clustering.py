try:
    import pyemma
except ImportError as e:
    raise ValueError('pyemma python module not avaiable. Please install it to use this function.')

import mdtraj as md
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import itertools
from scipy.ndimage import gaussian_filter
from ipywidgets import interact, fixed #FloatSlider, IntSlider, FloatRangeSlider, VBox, HBox, interactive_output, Dropdown, Checkbox

class ligand_msm:

    def __init__(self, pele_analysis):
        """
        MSM class for analysing ligand trajectories.
        """

        # Define attributes
        self.pele_analysis = pele_analysis
        self.trajectories = {}
        self.all_trajectories = []
        self.topology = {}
        self.ligand_atoms = {}
        self.features = {}
        self.data = {}
        self.tica_output = {}
        self.tica_concatenated = {}
        self.all_data = {}
        self.all_tica = {}
        self.all_tica_output = {}
        self.all_tica_concatenated = {}
        self.metric_features = {}

        # Get individual ligand-only trajectories
        print('Getting individual ligand trajectories')
        for protein, ligand in self.pele_analysis.pele_combinations:

            self.trajectories[(protein, ligand)], self.topology[ligand] = self.pele_analysis.getLigandTrajectoryPerTrajectory(protein, ligand, return_paths=True)

            # Gather all trajectories
            for t in self.trajectories[(protein, ligand)]:
                self.all_trajectories.append(t)

            # Get ligand atom names
            if ligand not in self.ligand_atoms:
                top_traj = md.load(self.topology[ligand])
                self.ligand_atoms[ligand] = [a.name for a in top_traj.topology.atoms]

            # Create featurizer
            if ligand not in self.features:
                self.features[ligand] = pyemma.coordinates.featurizer(self.topology[ligand])

    def addFeature(self, feature, ligand):
        """
        """
        implemented_features = ['positions', 'metrics']

        if feature not in implemented_features:
            raise ValueError('Feature %s not implemented. try: %s' % (feature, implemented_features))

        if feature == 'positions':
            self.features[ligand].add_selection(self.features[ligand].select('all'))

        if feature == 'metrics':

            # Add metric features to ligand
            if ligand not in self.metric_features:
                self.metric_features[ligand] = {}

            # Get metrics
            metrics = []
            for m in self.pele_analysis.data.keys():
                if m.startswith('metric_'):
                    metrics.append(m)

            # Get metrics data
            ligand_data = self.pele_analysis.data[self.pele_analysis.data.index.get_level_values('Ligand') == ligand]
            for protein in self.pele_analysis.proteins:

                # Add metric features to ligand
                if protein not in self.metric_features[ligand]:
                    self.metric_features[ligand][protein] = []

                protein_data = ligand_data[ligand_data.index.get_level_values('Protein') == protein]
                for trajectory in ligand_data.index.levels[3]:
                    trajectory_data = protein_data[protein_data.index.get_level_values('Trajectory') == trajectory]
                    self.metric_features[ligand][protein].append(trajectory_data[metrics].to_numpy())

    def getFeaturesData(self, ligand):
        """
        """
        if ligand not in self.data:
            self.data[ligand] = {}

        if ligand not in self.all_data:
            self.all_data[ligand] = []

        for protein in self.pele_analysis.proteins:

            self.data[ligand][protein] = pyemma.coordinates.load(self.trajectories[(protein, ligand)], features=self.features[ligand])

            # Add metric features
            if ligand in self.metric_features:
                for t in range(len(self.metric_features[ligand][protein])):

                    assert self.metric_features[ligand][protein][t].shape[0] == self.data[ligand][protein][t].shape[0]

                    self.data[ligand][protein][t] = np.concatenate([self.data[ligand][protein][t],
                                                    self.metric_features[ligand][protein][t]],
                                                    axis=1)
            self.all_data[ligand] += self.data[ligand][protein]

    def calculateTICA(self, ligand, lag_time):
        """
        """

        # Create TICA based on all ligand simulations
        self.all_tica[ligand] = pyemma.coordinates.tica(self.all_data[ligand], lag=lag_time)
        self.all_tica_output[ligand] = self.all_tica[ligand].get_output()
        self.all_tica_concatenated[ligand] = np.concatenate(self.all_tica_output[ligand])
        self.ndims = self.all_tica_concatenated[ligand].shape[1]

        # Transorm individual protein+ligand trajectories into TICA mammping
        if ligand not in self.tica_output:
            self.tica_output[ligand] = {}
        if ligand not in self.tica_concatenated:
            self.tica_concatenated[ligand] = {}
        for protein in self.data[ligand]:
            self.tica_output[ligand][protein] = self.all_tica[ligand].transform(self.data[ligand][protein])
            self.tica_concatenated[ligand][protein] = np.concatenate(self.tica_output[ligand][protein])

    def plotLagTimeVsTICADim(self, ligand, max_lag_time):
        lag_times = []
        dims = []
        for lt in range(1, max_lag_time+1):
            self.calculateTICA(ligand,lt)
            ndim = self.all_tica_concatenated[ligand].shape[1]
            lag_times.append(lt)
            dims.append(ndim)

        plt.figure(figsize=(4,2))
        Xa = np.array(lag_times)
        plt.plot(Xa,dims)
        plt.xlabel('Lag time [ns]', fontsize=12)
        plt.ylabel('Nbr. of dimensions holding\n95% of the kinetic variance', fontsize=12)

    def plotTICADistribution(self, ligand, max_tica=10):
        """
        """
        fig, axes = plt.subplots(1, 1, figsize=(12, max_tica))
        pyemma.plots.plot_feature_histograms(
            self.all_tica_concatenated[ligand][:,:max_tica],
            ax=axes,
            feature_labels=['IC'+str(i) for i in range(1, max_tica+1)],
            ylog=True)
        fig.tight_layout()

    def plotTICADensity(self, ligand, ndims=4):
        """
        """
        IC = {}
        for i in range(ndims):
            IC[i] = self.all_tica_concatenated[ligand][:, i]

        combinations = list(itertools.combinations(range(ndims), r=2))
        fig, axes = plt.subplots(len(combinations), figsize=(7, 5*len(combinations)), sharey=True, sharex=True)
        for i,c in enumerate(combinations):
            if len(combinations) <= 1:
                pyemma.plots.plot_density(*np.array([IC[c[0]], IC[c[1]]]), ax=axes, logscale=True)
                axes.set_xlabel('IC '+str(c[0]+1))
                axes.set_ylabel('IC '+str(c[1]+1))
            else:
                pyemma.plots.plot_density(*np.array([IC[c[0]], IC[c[1]]]), ax=axes[i], logscale=True)
                axes[i].set_xlabel('IC '+str(c[0]+1))
                axes[i].set_ylabel('IC '+str(c[1]+1))

    def getMetricData(self, ligand, protein, metric):
        """
        """
        metric_data = []
        ligand_data = self.pele_analysis.data[self.pele_analysis.data.index.get_level_values('Ligand') == ligand]
        protein_data = ligand_data[ligand_data.index.get_level_values('Protein') == protein]
        for trajectory in ligand_data.index.levels[3]:
            trajectory_data = protein_data[protein_data.index.get_level_values('Trajectory') == trajectory]
            metric_data.append(trajectory_data[metric].to_numpy())

        return metric_data

    def plotFreeEnergy(self, max_tica=10, metric_line=None, size=1.0, sigma=1.0, bins=100, xlim=None, ylim=None):
        """
        """
        def getLigands(Protein, max_tica=10, metric_line=None):
            ligands = []
            for protein, ligand in self.pele_analysis.pele_combinations:
                if Protein == 'all':
                    ligands.append(ligand)
                else:
                    if protein == Protein:
                        ligands.append(ligand)

            if Protein == 'all':
                ligands = list(set(ligands))

            interact(getCoordinates, Protein=fixed(Protein), Ligand=ligands, max_tica=fixed(max_tica),
                    metric_line=fixed(metric_line))

        def getCoordinates(Protein, Ligand, max_tica=10, metric_line=None):

            dimmensions = []
            # Add metrics
            for m in self.pele_analysis.data.keys():
                if m.startswith('metric_'):
                    dimmensions.append(m)

            # Add TICA dimmensions
            for i in range(max_tica):
                dimmensions.append('IC'+str(i+1))

            interact(_plotBindingEnergy, Protein=fixed(Protein), Ligand=fixed(Ligand), X=dimmensions, Y=dimmensions,
                     metric_line=fixed(metric_line))

        def _plotBindingEnergy(Protein, Ligand, X='IC1', Y='IC2', metric_line=None):

            if X.startswith('IC'):
                index = int(X.replace('IC', ''))-1
                input_data1 = self.tica_concatenated[Ligand][Protein][:, index]
                x_metric_line = None
            elif X.startswith('metric_'):
                input_data1 = np.concatenate(self.getMetricData(Ligand, Protein, X))
                x_metric_line = metric_line

            if Y.startswith('IC'):
                index = int(Y.replace('IC', ''))-1
                input_data2 = self.tica_concatenated[Ligand][Protein][:, index]
                y_metric_line = None
            elif Y.startswith('metric_'):
                input_data2 = np.concatenate(self.getMetricData(Ligand, Protein, Y))
                y_metric_line = metric_line

            _plot_Nice_PES(input_data1, input_data2, xlabel=X, ylabel=Y, bins=bins, size=size, sigma=sigma,
                           x_metric_line=x_metric_line, y_metric_line=y_metric_line, xlim=xlim, ylim=ylim)

        interact(getLigands, Protein=sorted(self.pele_analysis.proteins)+['all'], max_tica=fixed(max_tica),
                 metric_line=fixed(metric_line))

def _plot_Nice_PES(input_data1, input_data2, xlabel=None, ylabel=None, bins=90, sigma=0.99, title=False, size=1,
                   x_metric_line=None, y_metric_line=None, dpi=300, title_size=14, cmax=None, title_rotation=None,
                   title_location=None, title_x=0.5, title_y=1.02, show_xticks=False, show_yticks=False,
                   xlim=None, ylim=None):

    matplotlib.style.use("seaborn-paper")

    plt.figure(figsize=(4*size, 3.3*size), dpi=dpi)

    fig, ax = plt.subplots()

    # alldata1=np.vstack(input_data1)
    # alldata2=np.vstack(input_data2)

    min1=np.min(input_data1)
    max1=np.max(input_data1)
    min2=np.min(input_data2)
    max2=np.max(input_data2)

    z,x,y = np.histogram2d(input_data1, input_data2, bins=bins)
    z += 0.1

    # compute free energies
    F = -np.log(z)

    # contour plot
    extent = [x[0], x[-1], y[0], y[-1]]

    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['bottom'].set_visible(False)

    if not show_xticks:
        plt.xticks([])
    else:
        ax.spines['bottom'].set_visible(True)

    if not show_yticks:
        plt.yticks([])
    else:
        ax.spines['left'].set_visible(True)

    data = gaussian_filter((F.T)*0.592-np.min(F.T)*0.592, sigma)

    if cmax != None:
        levels=np.linspace(0, cmax, num=9)
    else:
        levels=np.linspace(0, np.max(data)-0.5, num=9)

    plt.contour(data, colors='black', linestyles='solid', alpha=0.7,
                cmap=None, levels=levels, extent=extent)

    cnt = plt.contourf(data, alpha=0.5, cmap='jet', levels=levels, extent=extent)

    plt.xlabel(xlabel, fontsize=10*size)
    plt.ylabel(ylabel, fontsize=10*size)

    if xlim != None:
        plt.xlim(xlim)
    if ylim != None:
        plt.ylim(ylim)

    if x_metric_line != None:
        plt.axvline(x_metric_line, ls='--', c='k')
    if y_metric_line != None:
        plt.axhline(y_metric_line, ls='--', c='k')

    if title:
        plt.title(title, fontsize = title_size*size, rotation=title_rotation,
                  loc=title_location, x=title_x, y=title_y)

    plt.subplots_adjust(bottom=0.1, right=0.8, top=0.8)

    cax = plt.axes([0.81, 0.1, 0.02, 0.7])

    cbar = plt.colorbar(cax=cax, format='%.1f')
    cbar.set_label('Free energy [kcal/mol]',
                   fontsize=10*size,
                   labelpad=5,
                   y=0.5)
    cax.axes.tick_params(labelsize=10*size)
