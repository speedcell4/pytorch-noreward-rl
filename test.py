import pickle
import time
from collections import deque

import torch
import torch.nn.functional as F
from torch.autograd import Variable

import env_wrapper
from model import ActorCritic


def test(rank, args, shared_model):
    torch.manual_seed(args.seed + rank)
    env = env_wrapper.create_doom(args.record, outdir=args.outdir)

    model = ActorCritic(env.observation_space.shape[0], env.action_space)

    model.eval()
    state = env.reset()
    state = torch.from_numpy(state)
    reward_sum = 0
    done = True

    start_time = time.time()

    # a quick hack to prevent the agent from stucking
    actions = deque(maxlen=2100)
    episode_length = 0
    result = []

    while True:
        episode_length += 1
        # Sync with the shared model
        if done:
            model.load_state_dict(shared_model.state_dict())
            cx = Variable(torch.zeros(1, 256), volatile=True)
            hx = Variable(torch.zeros(1, 256), volatile=True)
        else:
            cx = Variable(cx.data, volatile=True)
            hx = Variable(hx.data, volatile=True)

        value, logit, (hx, cx) = model(
            (Variable(state.unsqueeze(0), volatile=True), (hx, cx)),
            icm=False
        )

        prob = F.softmax(logit)
        action = prob.max(1)[1].data.numpy()

        state, reward, done, _ = env.step(action[0, 0])
        state = torch.from_numpy(state)

        done = done or episode_length >= args.max_episode_length
        reward_sum += reward

        # a quick hack to prevent the agent from stucking
        actions.append(action[0, 0])
        if actions.count(actions[0]) == actions.maxlen:
            done = True

        if done:
            end_time = time.time()
            print("Time {}, episode reward {}, episode length {}".format(
                time.strftime("%Hh %Mm %Ss",
                              time.gmtime(end_time - start_time)),
                reward_sum, episode_length))
            result.append((reward_sum, end_time - start_time))
            f = open('output/result.pickle', 'w')
            pickle.dump(result, f)
            f.close()
            torch.save(model.state_dict(), 'output/{}.pth'.format((end_time - start_time)))

            reward_sum = 0
            episode_length = 0
            actions.clear()
            state = env.reset()
            state = torch.from_numpy(state)
            time.sleep(60)
