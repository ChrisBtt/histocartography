from typing import Dict, Tuple

import dgl
import torch
import torchvision
from histocartography.ml.layers.multi_layer_gnn import MultiLayerGNN
from torch import nn

from constants import GNN_NODE_FEAT_IN, GNN_NODE_FEAT_OUT
from utils import dynamic_import_from


class ClassifierHead(nn.Module):
    """A basic classifier head"""

    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        n_layers: int = 2,
        hidden_dim: int = None,
    ) -> None:
        """Create a basic classifier head

        Args:
            input_dim (int): Dimensionality of the input
            output_dim (int): Number of output classes
            n_layers (int, optional): Number of layers (including input to hidden and hidden to output layer). Defaults to 2.
            hidden_dim (int, optional): Dimensionality of the hidden layers. Defaults to None.
        """
        super().__init__()
        if hidden_dim is None:
            hidden_dim = input_dim
        modules = [nn.Linear(input_dim, hidden_dim), nn.ReLU()]
        for _ in range(n_layers - 2):
            modules.append(nn.Linear(hidden_dim, hidden_dim))
            modules.append(nn.ReLU())
        modules.append(nn.Linear(hidden_dim, output_dim))
        self.model = nn.Sequential(*modules)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Do a forward pass through the classifier head

        Args:
            x (torch.Tensor): Input tensor

        Returns:
            torch.Tensor: Output tensor
        """
        return self.model(x)


class NodeClassifierHead(nn.Module):
    def __init__(self, latent_dim: int, node_classifier_config: Dict, nr_classes: int = 4) -> None:
        super().__init__()
        node_classifiers = [
            ClassifierHead(
                input_dim=latent_dim, output_dim=1, **node_classifier_config
            )
            for _ in range(nr_classes)
        ]
        self.node_classifiers = nn.ModuleList(node_classifiers)
    
    def forward(self, node_embedding: torch.Tensor) -> torch.Tensor:
        node_logit = torch.empty(
            (node_embedding.shape[0], len(self.node_classifiers)), device=node_embedding.device
        )
        for i, node_classifier in enumerate(self.node_classifiers):
            classifier_output = node_classifier(node_embedding).squeeze(1)
            node_logit[:, i] = classifier_output
        return node_logit


class GraphClassifierHead(nn.Module):
    def __init__(self, latent_dim: int, graph_classifier_config: Dict, nr_classes: int = 4) -> None:
        super().__init__()
        self.graph_classifier = ClassifierHead(
            input_dim=latent_dim,
            output_dim=nr_classes,
            **graph_classifier_config,
        )

    def forward(self, graph_embedding: torch.Tensor) -> torch.Tensor:
        return self.graph_classifier(graph_embedding)


class SuperPixelTissueClassifier(nn.Module):
    def __init__(self, gnn_config: Dict,
        node_classifier_config: Dict,
        nr_classes: int = 4,
    ) -> None:
        super().__init__()
        self.gnn_model = MultiLayerGNN(gnn_config)
        if gnn_config["agg_operator"] in ["none", "lstm"]:
            latent_dim = gnn_config["output_dim"]
        elif gnn_config["agg_operator"] in ["concat"]:
            latent_dim = gnn_config["output_dim"] * gnn_config["n_layers"]
        else:
            raise NotImplementedError(
                f"Only supported agg operators are [none, lstm, concat]"
            )
        self.node_classifier = NodeClassifierHead(latent_dim, node_classifier_config, nr_classes)

    def forward(self, graph: dgl.DGLGraph) -> torch.Tensor:
        in_features = graph.ndata[GNN_NODE_FEAT_IN]
        self.gnn_model(graph, in_features)
        node_embedding = graph.ndata[GNN_NODE_FEAT_OUT]
        node_logit = self.node_classifier(node_embedding)
        return node_logit


class SemiSuperPixelTissueClassifier(nn.Module):
    """Classifier that uses both weak graph labels and some provided node labels"""

    def __init__(
        self,
        gnn_config: Dict,
        graph_classifier_config: Dict,
        node_classifier_config: Dict,
        nr_classes: int = 4,
    ) -> None:
        """Build a classifier to classify superpixel tissue graphs

        Args:
            config (Dict): Configuration of the models
            nr_classes (int, optional): Number of classes to consider. Defaults to 4.
        """
        super().__init__()
        self.gnn_model = MultiLayerGNN(gnn_config)
        if gnn_config["agg_operator"] in ["none", "lstm"]:
            latent_dim = gnn_config["output_dim"]
        elif gnn_config["agg_operator"] in ["concat"]:
            latent_dim = gnn_config["output_dim"] * gnn_config["n_layers"]
        else:
            raise NotImplementedError(
                f"Only supported agg operators are [none, lstm, concat]"
            )
        self.graph_classifier = GraphClassifierHead(latent_dim, graph_classifier_config, nr_classes)
        self.node_classifiers = NodeClassifierHead(latent_dim, node_classifier_config, nr_classes)

    def forward(self, graph: dgl.DGLGraph) -> Tuple[torch.Tensor, torch.Tensor]:
        """Perform a forward pass on the graph

        Args:
            graph (dgl.DGLGraph): Input graph with node features in GNN_NODE_FEAT_IN

        Returns:
            Tuple[torch.Tensor, torch.Tensor]: Logits of the graph classifier, logits of the node classifiers
        """
        in_features = graph.ndata[GNN_NODE_FEAT_IN]
        graph_embedding = self.gnn_model(graph, in_features)
        graph_logit = self.graph_classifier(graph_embedding)
        node_embedding = graph.ndata[GNN_NODE_FEAT_OUT]
        node_logit = self.node_classifiers(node_embedding)
        return graph_logit, node_logit


class ImageTissueClassifier(nn.Module):
    """Classifier that uses both weak graph labels and some provided node labels"""

    def __init__(
        self,
        gnn_config: Dict,
        graph_classifier_config: Dict,
        nr_classes: int = 4,
    ) -> None:
        """Build a classifier to classify superpixel tissue graphs

        Args:
            config (Dict): Configuration of the models
            nr_classes (int, optional): Number of classes to consider. Defaults to 4.
        """
        super().__init__()
        self.gnn_model = MultiLayerGNN(gnn_config)
        if gnn_config["agg_operator"] in ["none", "lstm"]:
            latent_dim = gnn_config["output_dim"]
        elif gnn_config["agg_operator"] in ["concat"]:
            latent_dim = gnn_config["output_dim"] * gnn_config["n_layers"]
        else:
            raise NotImplementedError(
                f"Only supported agg operators are [none, lstm, concat]"
            )
        self.graph_classifier = GraphClassifierHead(latent_dim, graph_classifier_config, nr_classes)

    def forward(self, graph: dgl.DGLGraph) -> Tuple[torch.Tensor, torch.Tensor]:
        """Perform a forward pass on the graph

        Args:
            graph (dgl.DGLGraph): Input graph with node features in GNN_NODE_FEAT_IN

        Returns:
            Tuple[torch.Tensor, torch.Tensor]: Logits of the graph classifier, logits of the node classifiers
        """
        in_features = graph.ndata[GNN_NODE_FEAT_IN]
        graph_embedding = self.gnn_model(graph, in_features)
        graph_logit = self.graph_classifier(graph_embedding)
        return graph_logit


class PatchTissueClassifier(nn.Module):
    def __init__(self, **kwargs) -> None:
        super().__init__()
        self.model = self._select_model(**kwargs)

    @staticmethod
    def _select_model(
        architecture: str, num_classes: int, dropout: int, freeze: int = 0, **kwargs
    ) -> Tuple[nn.Module, int]:
        """Returns the model and number of features for a given name

        Args:
            architecture (str): Name of architecture. Can be [resnet{18,34,50,101,152}, vgg{16,19}]

        Returns:
            Tuple[nn.Module, int]: The model and the number of features
        """
        model_class = dynamic_import_from("torchvision.models", architecture)
        model = model_class(**kwargs)
        if isinstance(model, torchvision.models.resnet.ResNet):
            feature_dim = model.fc.in_features
            model.fc = nn.Linear(feature_dim, num_classes)
            for layer in list(model.children())[:freeze]:
                for param in layer.parameters():
                    param.requires_grad = False
        else:
            feature_dim = model.classifier[-1].in_features
            model.classifier = nn.Sequential(
                nn.Dropout(p=dropout),
                nn.Linear(feature_dim, num_classes)
            )
            for param in model.features[:freeze].parameters():
                param.requires_grad = False
        return model

    def forward(self, x):
        return self.model(x)
