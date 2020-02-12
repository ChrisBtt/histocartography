from PIL import ImageDraw
import numpy as np
import dgl

from histocartography.utils.io import show_image, save_image, complete_path
from histocartography.utils.draw_utils import draw_ellipse, draw_line, draw_poly
from histocartography.ml.layers.constants import CENTROID


class GraphVisualization:

    def __init__(self, show=False, save=True):
        print('Initialize graph visualizer')
        self.show = show
        self.save = save
        self.save_path = '/Users/frd/Documents/Code/Projects/Experiments/data_dummy_sp/graphs/'

    def __call__(self, show_cg, show_superpx, data, size):

        for index in range(size):

            image = data[-2][index]
            image_name = data[-1][index]
            draw = ImageDraw.Draw(image, 'RGBA')

            if show_superpx:
                superpx_graph = dgl.unbatch(data[1])[index] if show_cg else dgl.unbatch(data[0])[index]
                superpx_map = data[2] if show_cg else data[1]

                # get centroids and edges
                cent_sp, edges_sp = self._get_centroid_and_edges(superpx_graph)
                self.draw_superpx(superpx_map, draw)
                self.draw_centroid(cent_sp, draw, (0, 255, 0))
                self.draw_edges(cent_sp, edges_sp, draw, (0, 255, 0), 2)

            if show_cg:
                cell_graph = dgl.unbatch(data[0])[index]

                # get centroids and edges
                cent_cg, edges_cg = self._get_centroid_and_edges(cell_graph)

                # draw centroids
                self.draw_centroid(cent_cg, draw, (0, 255, 255))
                self.draw_edges(cent_cg, edges_cg, draw, (0, 255, 255), 5)

            if self.show:
                show_image(image)

            if self.save:
                save_image(image, fname=complete_path(self.save_path, image_name + '.png'))

        return image

    @staticmethod
    def draw_centroid(centroids, draw_bd, fill):
        for centroid in centroids:
            centroid = [centroid[0].item(), centroid[1].item()]
            draw_ellipse(centroid, draw_bd, fill)

    @staticmethod
    def draw_edges(centroids, edges, draw_bd, fill, width):
        for edge in edges:
            src_centroid = [centroids[edge[0]][0].item(), centroids[edge[0]][1].item()]
            dst_centroid = [centroids[edge[1]][0].item(), centroids[edge[1]][1].item()]
            draw_line(src_centroid, dst_centroid, draw_bd, fill, width)

    @staticmethod
    def draw_superpx(mask, draw_bd):
        px_list = list(np.unique(mask))
        for idx, px_id in enumerate(px_list):
            rows, columns = np.where(mask == px_id)
            list_coord = np.asarray([[columns[i].item(), rows[i].item()] for i in range(len(rows))])
            xy = list_coord.flatten().tolist()
            draw_poly(xy, draw_bd)

    @staticmethod
    def _get_centroid_and_edges(graph):
        centroids = graph.ndata[CENTROID]
        src, dst = graph.edges()
        edges = [(s.item(), d.item()) for (s, d) in zip(src, dst)]
        return centroids, edges
