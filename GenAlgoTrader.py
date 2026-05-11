import pygad
import numpy as np
import random
import BSE as bse
import sys

NUM_GENES = 5
GENE_BOUNDS = {-1.0, 1.0}

class GATrader(bse.Trader):
    def __init__(self, ttype, tid, balance, params):
        super().__init__(ttype, tid, balance, params)

        self.sessionProfit = 0.0
        if isinstance(params, dict) and "genes" in params:
            self.genes = np.array(params["genes"], dtype=float)
        else:
            self.genes = np.random.uniform(GENE_BOUNDS[0], GENE_BOUNDS[1], size=NUM_GENES)
        
        # gene = self.genes
        self.shadeFactor = self.genes[0]
        self.lobBidW = self.genes[1]
        self.lobAskW = self.genes[2]
        self.spreadSensitivity = self.genes[3]
        self.aggression = self.genes[4]
    
    def getQuote(self, lob, order):
        limit = order.price
        oType = order.otype

        bestBid = lob["bids"]["best"] if lob["bids"]["best"] is not None else limit
        bestAsk = lob["asks"]["best"] if lob["asks"]["best"] is not None else limit
        mid = (bestBid + bestAsk) / 2
        spread = (bestAsk - bestBid) if (bestAsk is not None and bestBid is not None and (bestAsk-bestBid) >= 1) else 1
        relPos = (limit - mid) / spread

        weightSig = (self.lobBidW * (bestBid / limit)) + (self.lobAskW * (bestAsk / limit)) + (self.spreadSensitivity * (spread / limit)) + (self.aggression * relPos)
        shade = self.shadeFactor * weightSig * 0.1

        if oType == "Bid":
            quote = limit * (1.0 + shade)
            quote = min(quote, limit)
        else:
            quote = limit * (1.0 - shade)
            quote = max(quote, limit)
        return int(round(quote))
    
    def getorder(self, time, countdown, lob):
        # this test for negative countdown is purely to stop PyCharm warning about unused parameter value
        if countdown < 0:
            sys.exit('Negative countdown')

        if len(self.orders) < 1:
            # no orders: return NULL
            order = None
        else:
            order = self.orders[0] # assumes there is only ever 1 order
            qid = lob["QID"]
            quotePrice = self.getQuote(lob, order)
            order = bse.Order(self.tid, order.otype, quotePrice, self.orders[0].qty, time, qid)
            self.lastquote = order
        return order
    
    def respond(self, time, lob, trade, vrbs):
        self.profitpertime = self.profitpertime_update(time, self.birthtime, self.balance)
        return None

    def bookkeep(self, trade, order, vrbs, time):
        outstr = ""
        for order in self.orders:
            outstr = outstr + str(order)
        self.blotter.append(trade)

        profit = 0.0
        if order.otype == "Bid":
            profit = order.price - trade["price"]
        else:
            profit = trade["price"] - order.price
        
        self.balance += profit
        self.sessionProfit += profit
        self.n_trades += 1
        self.profitpertime = self.balance / (time - self.birthtime)

        if profit < 0:
            print(profit)
            print(trade)
            print(order)
            sys.exit('FAIL: negative profit')

        if vrbs:
            print(f"{outstr} profit={profit} balance={self.balance} profit/time={str(self.profitpertime)}" % (outstr, profit, self.balance, str(self.profitpertime)))
        self.del_order(order)


class GAEvolver:
    def __init__(self, popSize=20, numGen=30, sessionBuilder=None):
        self.popSize = popSize
        self.numGen = numGen
        self.sessionBuilder = sessionBuilder
        self.bestGene = None
        self.ga = None
    
    def fitness(self, ga, solution):
        profit = self.sessionBuilder(solution)
        return float(profit)
    
    def evolve(self):
        self.ga = pygad.GA(
            num_generations=self.numGen,
            num_parents_mating=max(2, self.popSize // 4),
            fitness_func=self.fitness,
            sol_per_pop=self.popSize,
            num_genes=NUM_GENES,
            gene_space=GENE_BOUNDS,
            parent_selection_type="tournament",
            crossover_probability="single_point",
            mutation_type="random",
            mutation_probability=0.15,
            keep_elitism=2,
            stop_criteria=f"saturate_{self.numGen // 3}",
            parallel_processing=None,
        )
        self.ga.run()
        solution, fitness, solIndex = self.ga.instance.best_solution()
        self.bestGene = solution
        print(f"GA Trader Best Profit: {fitness:.4f}")
        print(f"GA Trader Best Gene: {solution}")

    def plot(self):
        if self.ga:
            self.ga.plot_fitness()
        