# Copyright (c) 2019, NVIDIA CORPORATION. All rights reserved.
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
import os
import math
from test_utils import get_gpu_num
from test_utils import get_dali_extra_path

import nvidia.dali.ops as ops
import nvidia.dali.types as types
from nvidia.dali.backend_impl import TensorListGPU
from nvidia.dali.pipeline import Pipeline
import nvidia.dali.fn as fn
import re
import tempfile
import fractions

from nose.tools import assert_raises, raises

VIDEO_DIRECTORY = "/tmp/video_files"
PLENTY_VIDEO_DIRECTORY = "/tmp/many_video_files"
VIDEO_FILES = os.listdir(VIDEO_DIRECTORY)
PLENTY_VIDEO_FILES=  os.listdir(PLENTY_VIDEO_DIRECTORY)
VIDEO_FILES = [VIDEO_DIRECTORY + '/' + f for f in VIDEO_FILES]
PLENTY_VIDEO_FILES = [PLENTY_VIDEO_DIRECTORY + '/' + f for f in PLENTY_VIDEO_FILES]
FILE_LIST = "/tmp/file_list.txt"
MUTLIPLE_RESOLUTION_ROOT = '/tmp/video_resolution/'

test_data_root = os.environ['DALI_EXTRA_PATH']
video_data_root = os.path.join(test_data_root, 'db', 'video')
corrupted_video_data_root = os.path.join(video_data_root, 'corrupted')

ITER=6
LONG_ITER=600
BATCH_SIZE=4
COUNT=5


class VideoPipe(Pipeline):
    def __init__(self, batch_size, data, shuffle=False, stride=1, step=-1, device_id=0, num_shards=1,
                 dtype=types.FLOAT, sequence_length=COUNT):
        super(VideoPipe, self).__init__(batch_size, num_threads=2, device_id=device_id, seed=12)
        self.input = ops.VideoReader(device="gpu", filenames=data, sequence_length=sequence_length,
                                     shard_id=0, num_shards=num_shards, random_shuffle=shuffle,
                                     normalized=True, image_type=types.YCbCr, dtype=dtype,
                                     step=step, stride=stride)

    def define_graph(self):
        output = self.input(name="Reader")
        return output

class LabeledVideoPipe(Pipeline):
    def __init__(self, batch_size, data, shuffle=False, stride=1, step=-1, device_id=0, num_shards=1,
                 interleave_size=0, interleave_mode="shorten", dtype=types.FLOAT, sequence_length=COUNT):
        super(LabeledVideoPipe, self).__init__(batch_size, num_threads=2, device_id=device_id, seed=12)
        self.input = ops.VideoReader(device="gpu", filenames=data, sequence_length=sequence_length,
                                     interleave_size=interleave_size, interleave_mode=interleave_mode,
                                     labels=[k for k in range(len(data))], enable_frame_num=True, 
                                     shard_id=0, num_shards=num_shards, random_shuffle=shuffle,
                                     normalized=True, image_type=types.YCbCr, dtype=dtype,
                                     step=step, stride=stride)

    def define_graph(self):
        output = self.input(name="Reader")
        return output

class VideoPipeList(Pipeline):
    def __init__(self, batch_size, data, device_id=0, sequence_length=COUNT, step=-1, stride=1):
        super(VideoPipeList, self).__init__(batch_size, num_threads=2, device_id=device_id)
        self.input = ops.VideoReader(device="gpu", file_list=data, sequence_length=sequence_length,
                                     step=step, stride=stride, file_list_frame_num=True)

    def define_graph(self):
        output = self.input(name="Reader")
        return output

class VideoPipeRoot(Pipeline):
    def __init__(self, batch_size, data, device_id=0, sequence_length=COUNT):
        super(VideoPipeRoot, self).__init__(batch_size, num_threads=2, device_id=device_id)
        self.input = ops.VideoReader(device="gpu", file_root=data, sequence_length=sequence_length,
                                     random_shuffle=True)

    def define_graph(self):
        output = self.input(name="Reader")
        return output

def test_simple_videopipeline():
    pipe = VideoPipe(batch_size=BATCH_SIZE, data=VIDEO_FILES)
    pipe.build()
    for i in range(ITER):
        print("Iter " + str(i))
        out = pipe.run()
        assert(out[0].layout() == "FHWC")
    del pipe

def test_wrong_length_sequence_videopipeline():
    pipe = VideoPipe(batch_size=BATCH_SIZE, data=VIDEO_FILES, sequence_length=100000)
    assert_raises(RuntimeError, pipe.build)

def check_videopipeline_supported_type(dtype):
    pipe = VideoPipe(batch_size=BATCH_SIZE, data=VIDEO_FILES, dtype=dtype)
    pipe.build()
    for i in range(ITER):
        print("Iter " + str(i))
        _ = pipe.run()
    del pipe

SUPPORTED_TYPES = [types.DALIDataType.FLOAT, types.DALIDataType.UINT8]
ALL_TYPES = list(types.DALIDataType.__members__.values())

def test_simple_videopipeline_supported_types():
    for type in SUPPORTED_TYPES:
        yield check_videopipeline_supported_type, type

def test_simple_videopipeline_not_supported_types():
    for type in set(ALL_TYPES) - set(SUPPORTED_TYPES):
        yield assert_raises, RuntimeError, check_videopipeline_supported_type, type

def test_file_list_videopipeline():
    pipe = VideoPipeList(batch_size=BATCH_SIZE, data=FILE_LIST)
    pipe.build()
    for i in range(ITER):
        print("Iter " + str(i))
        _ = pipe.run()
    del pipe

def _test_file_list_starts_videopipeline(start, end):
    files = sorted(os.listdir(VIDEO_DIRECTORY))
    list_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
    list_file.write("{} {}\n".format(os.path.join(VIDEO_DIRECTORY, files[0]), 0))
    list_file.close()

    pipe = VideoPipeList(batch_size=BATCH_SIZE, data=list_file.name, sequence_length=1)
    pipe.build()
    reference_seq_num = pipe.reader_meta("Reader")["epoch_size"]
    del pipe
    os.remove(list_file.name)

    list_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
    if end is None:
        list_file.write("{} {} {}\n".format(os.path.join(VIDEO_DIRECTORY, files[0]), 0, start))
    else:
        list_file.write("{} {} {} {}\n".format(os.path.join(VIDEO_DIRECTORY, files[0]), 0, start, end))
    list_file.close()

    pipe = VideoPipeList(batch_size=BATCH_SIZE, data=list_file.name, sequence_length=1)
    pipe.build()
    seq_num = pipe.reader_meta("Reader")["epoch_size"]

    expected_seq_num = reference_seq_num
    if start > 0:
        expected_seq_num -= start
    elif start < 0:
        expected_seq_num = -start

    if end is not None:
        if end > 0:
            expected_seq_num -= (reference_seq_num - end)
        elif end < 0:
            expected_seq_num += end

    assert expected_seq_num == seq_num, "Reference is {}, expected is {}, obtained {}".format(reference_seq_num, expected_seq_num, seq_num)
    os.remove(list_file.name)

def test_file_list_starts_ends_videopipeline():
    ranges = [
        [0, None],
        [1, None],
        [0, -1],
        [2, None],
        [0, -2],
        [0, 1],
        [-1, None],
        [-3, -1]
    ]
    for r in ranges:
        yield _test_file_list_starts_videopipeline, r[0], r[1]

def _test_file_list_empty_videopipeline(start, end):
    files = sorted(os.listdir(VIDEO_DIRECTORY))
    list_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
    if end is None:
        list_file.write("{} {} {}\n".format(os.path.join(VIDEO_DIRECTORY, files[0]), 0, start))
    else:
        list_file.write("{} {} {} {}\n".format(os.path.join(VIDEO_DIRECTORY, files[0]), 0, start, end))
    list_file.close()

    pipe = VideoPipeList(batch_size=BATCH_SIZE, data=list_file.name)
    assert_raises(RuntimeError, pipe.build)
    os.remove(list_file.name)

def test_file_list_empty_videopipeline():
    invalid_ranges = [
        [0, 0],
        [10, 10],
        [-1, 1],
        [1000000, None],
        [0, -1000]
    ]
    for r in invalid_ranges:
        yield _test_file_list_empty_videopipeline, r[0], r[1]

def test_step_video_pipeline():
    pipe = VideoPipe(batch_size=BATCH_SIZE, data=VIDEO_FILES, step=1)
    pipe.build()
    for i in range(ITER):
        print("Iter " + str(i))
        _ = pipe.run()
    del pipe

def test_stride_video_pipeline():
    pipe = VideoPipe(batch_size=BATCH_SIZE, data=VIDEO_FILES, stride=3)
    pipe.build()
    for i in range(ITER):
        print("Iter " + str(i))
        _ = pipe.run()
    del pipe

def test_multiple_resolution_videopipeline():
    pipe = VideoPipeRoot(batch_size=BATCH_SIZE, data=MUTLIPLE_RESOLUTION_ROOT)
    try:
        pipe.build()
        for i in range(ITER):
            print("Iter " + str(i))
            _ = pipe.run()
    except Exception as e:
        if str(e) == "Decoder reconfigure feature not supported":
            print("Multiple resolution test skipped")
        else:
            raise
    del pipe

def test_multi_gpu_video_pipeline():
    gpus = get_gpu_num()
    pipes = [VideoPipe(batch_size=BATCH_SIZE, data=VIDEO_FILES, device_id=d, num_shards=gpus) for d in range(gpus)]
    for p in pipes:
        p.build()
        p.run()

# checks if the VideoReader can handle more than OS max open file limit of opened files at once
def test_plenty_of_video_files():
    # make sure that there is one sequence per video file
    pipe = VideoPipe(batch_size=BATCH_SIZE, data=PLENTY_VIDEO_FILES, step=1000000, sequence_length=1)
    pipe.build()
    iters = math.ceil(len(os.listdir(PLENTY_VIDEO_DIRECTORY)) / BATCH_SIZE)
    for i in range(iters):
        print("Iter " + str(i))
        pipe.run()

@raises(RuntimeError)
def check_corrupted_videos():
    corrupted_videos = [corrupted_video_data_root + '/' + f for f in os.listdir(corrupted_video_data_root)]
    for corrupted in corrupted_videos:
        pipe = Pipeline(batch_size=BATCH_SIZE, num_threads=4, device_id=0)
        with pipe:
            vid = fn.video_reader(device="gpu", filenames=corrupted, sequence_length=1)
            pipe.set_outputs(vid)
        pipe.build()

def test_corrupted_videos():
    check_corrupted_videos()

@raises(RuntimeError)
def _test_wrong_interleave_size(interleave_size):
    pipe = LabeledVideoPipe(batch_size=BATCH_SIZE, data=VIDEO_FILES, sequence_length=1,
                            interleave_size=interleave_size, interleave_mode="shorten")
    pipe.build()

def _test_interleave_size(interleave_size):
    pipe = LabeledVideoPipe(batch_size=BATCH_SIZE, data=VIDEO_FILES, sequence_length=1,
                            interleave_size=interleave_size, interleave_mode="shorten")
    pipe.build()

def test_wrong_interleave_size():
    sizes = [
        -1,
        # x / (x - 1) should be non divisible without rest for all cases except 0
        len(VIDEO_FILES) - 1,

        # is bigger than the provided amount of videos
        len(VIDEO_FILES) + 1
    ]
    for i in range(1, len(VIDEO_FILES) + 1):
        if len(VIDEO_FILES) % i != 0:
            sizes.append(i)

    for size in sizes:
        yield _test_interleave_size, size

def test_interleave_size():
    sizes = [0]
    for i in range(1, len(VIDEO_FILES) + 1):
        if len(VIDEO_FILES) % i == 0:
            sizes.append(i)

    for size in sizes:
        yield _test_interleave_size, size

def test_interleave_batch_size():
    size = len(VIDEO_FILES)
    sequence_length = 1
    for i in range(3, len(VIDEO_FILES) + 1):
        if len(VIDEO_FILES) % i == 0:
            size = i
            break

    pipe = LabeledVideoPipe(batch_size=size * 2, data=VIDEO_FILES,
                            sequence_length=sequence_length,
                            interleave_size=size, interleave_mode="shorten")
    pipe.build()

    _, labels, time = pipe.run()
    labels = [int(x) for x in labels.as_cpu().as_array()]
    time   = [int(x) for x in time.as_cpu().as_array()]

    assert(len(set(labels)) == size)
    assert(len(set(time)) == 2)
    assert(all(time[i] + sequence_length == time[i + size] for i in range(size)))

@raises(RuntimeError)
def check_wrong_interleave_mode(mode):
    pipe = LabeledVideoPipe(batch_size=BATCH_SIZE, data=VIDEO_FILES, sequence_length=1,
                            interleave_size=-1, interleave_mode=mode)
    pipe.build()

def test_wrong_interleave_mode():
    check_wrong_interleave_mode("default")

def _test_interleave_mode(test_func):
    sizes = []
    for i in range(1, len(VIDEO_FILES) + 1):
        if len(VIDEO_FILES) % i == 0:
            sizes.append(i)
    lengths = [1, 2]

    for size in sizes:
        for length in lengths:
            test_func(size, length, ITER)

    size = len(VIDEO_FILES)
    for i in range(3, len(VIDEO_FILES) + 1):
        if len(VIDEO_FILES) % i == 0:
            size = i
            break
    test_func(size, 40, LONG_ITER)

def _test_continuous_interleave_mode(test_func):
    size = len(VIDEO_FILES)
    for i in range(3, len(VIDEO_FILES) + 1):
        if len(VIDEO_FILES) % i == 0:
            size = i
            break
    test_func(size, 40, LONG_ITER)

def _test_shorten_interleave_mode(batch_size, sequence_length, iters):
    assert(len(VIDEO_FILES) % batch_size == 0)
    pipe = LabeledVideoPipe(batch_size=batch_size, data=VIDEO_FILES,
                            sequence_length=sequence_length,
                            interleave_size=batch_size,
                            interleave_mode="shorten",
                            shuffle=False)
    pipe.build()
    
    last_time   = [-sequence_length for _ in range(batch_size)]
    last_labels = [-batch_size + i  for i in range(batch_size)]
    run_once = False

    for i in range(iters):
        _, labels, time = pipe.run()
        labels = labels.as_cpu().as_array()
        time   = time.as_cpu().as_array()
        print(labels.flatten(), time.flatten())
        
        assert(len(set(int(t) for t in time)) == 1)
        assert(len(set(int(label) for label in labels)) == len(labels))
        for k in range(batch_size):
            if labels[k] == last_labels[k]:
                assert(time[k] == last_time[k] + sequence_length)
            else:
                assert(labels[k] == last_labels[k] + batch_size)
                assert(time[k] == 0)
                
                if run_once:
                    # reached a boundary no need for further testing
                    del pipe
                    return

            last_labels[k] = labels[k]
            last_time[k] = time[k]
        run_once = True

def _test_repeat_interleave_mode(batch_size, sequence_length, iters):
    assert(len(VIDEO_FILES) % batch_size == 0)
    pipe = LabeledVideoPipe(batch_size=batch_size, data=VIDEO_FILES,
                            sequence_length=sequence_length,
                            interleave_size=batch_size,
                            interleave_mode="repeat",
                            shuffle=False)
    pipe.build()
    
    last_time   = [-sequence_length for _ in range(batch_size)]
    last_labels = [-batch_size + i  for i in range(batch_size)]
    run_once = False

    for i in range(iters):
        _, labels, time = pipe.run()
        labels = labels.as_cpu().as_array()
        time   = time.as_cpu().as_array()
        print(labels.flatten(), time.flatten())

        assert(len(set(int(label) for label in labels)) == len(labels))
        for k in range(batch_size):
            if labels[k] == last_labels[k]:
                # we either add the time or repeat.
                # if we repeat we restart at zero and at least on other video has to
                # be non zero as we would change the batch otherwise.
                assert(time[k] == last_time[k] + sequence_length or time[k] == 0)
                assert(any(time[j] != 0 for j in range(batch_size)))
            else:
                assert(labels[k] == last_labels[k] + batch_size)
                assert(all(time[j] == 0 for j in range(batch_size)))
                
                if run_once:
                    # reached a boundary no need for further testing
                    del pipe
                    return

            last_labels[k] = labels[k]
            last_time[k] = time[k]
        run_once = True

def _test_clamp_interleave_mode(batch_size, sequence_length, iters):
    assert(len(VIDEO_FILES) % batch_size == 0)
    pipe = LabeledVideoPipe(batch_size=batch_size, data=VIDEO_FILES,
                            sequence_length=sequence_length,
                            interleave_size=batch_size,
                            interleave_mode="clamp",
                            shuffle=False)
    pipe.build()
    
    last_time   = [-sequence_length for _ in range(batch_size)]
    max_time    = [0 for _ in range(batch_size)]
    last_labels = [-batch_size + i  for i in range(batch_size)]
    run_once = False

    for i in range(iters):
        _, labels, time = pipe.run()
        labels = labels.as_cpu().as_array()
        time   = time.as_cpu().as_array()
        print(labels.flatten(), time.flatten())

        assert(len(set(int(label) for label in labels)) == len(labels))
        for k in range(batch_size):
            if labels[k] == last_labels[k]:
                # we either add the time or repeat.
                # if we repeat we restart at zero and at least on other video has to
                # be non zero as we would change the batch otherwise.
                assert(time[k] == last_time[k] + sequence_length or time[k] == max_time[k])
                assert(any(time[j] != 0 for j in range(batch_size)))
            else:
                assert(labels[k] == last_labels[k] + batch_size)
                assert(all(time[j] == 0 for j in range(batch_size)))

                if run_once:
                    # reached a boundary no need for further testing
                    del pipe
                    return

            last_labels[k] = labels[k]
            last_time[k] = time[k]
            max_time[k] = max(max_time[k], time[k])
        run_once = True

def _test_shorten_continuous_interleave_mode(batch_size, sequence_length, iters):
    assert(len(VIDEO_FILES) % batch_size == 0)
    pipe = LabeledVideoPipe(batch_size=batch_size, data=VIDEO_FILES,
                            sequence_length=sequence_length,
                            interleave_size=batch_size,
                            interleave_mode="shorten_continuous",
                            shuffle=False)
    pipe.build()
    
    last_times  = [-sequence_length for _ in range(batch_size)]
    last_labels = [-batch_size + i  for i in range(batch_size)]
    end_labels  = [len(VIDEO_FILES) - i - 1 for i in range(batch_size)]
    init_labels = [i for i in range(batch_size)]
    last_data   = []
    run_through = False
    for i in range(iters):
        _, labels, time = pipe.run()
        labels = labels.as_cpu().as_array()
        time   = time.as_cpu().as_array()
        last_data.append((labels, time))
        if len(last_data) > 2: last_data.pop(0)
        print(labels.flatten(), time.flatten())

        assert(len(set(int(label) for label in labels)) == len(labels))
        for k in range(batch_size):
            if labels[k] == last_labels[k]:
                assert(time[k] == last_times[k] + sequence_length)
            elif run_through and all(labels[j] == init_labels[j] for j in range(batch_size)):
                # Reached the end of the video data
                # here all time stamps must be zero and because
                # we shortened the sequences. Thus, all last sequences must 
                # have the same length.
                last_label, last_time = last_data[-1]
                assert(all(time[k] == 0 for k in range(batch_size)))
                assert(len(set([int(last_time[k]) for k in range(batch_size)])) == 1)

                # no need for further testing.
                del pipe
                return
            else:
                assert(labels[k] == last_labels[k] + batch_size)
                assert(time[k] == 0)

            # we can be sure that we run through the data once
            # if we got at least one label that belongs to
            # the last of the videos.
            run_through = True if labels[k] == end_labels[k] else run_through
            last_labels[k] = labels[k]
            last_times[k] = time[k]
    del pipe

def _test_repeat_continuous_interleave_mode(batch_size, sequence_length, iters):
    assert(len(VIDEO_FILES) % batch_size == 0)
    pipe = LabeledVideoPipe(batch_size=batch_size, data=VIDEO_FILES,
                            sequence_length=sequence_length,
                            interleave_size=batch_size,
                            interleave_mode="repeat_continuous",
                            shuffle=False)
    pipe.build()
    
    last_times  = [-sequence_length for _ in range(batch_size)]
    last_labels = [-batch_size + i  for i in range(batch_size)]
    end_labels = [len(VIDEO_FILES) - i - 1 for i in range(batch_size)]
    init_labels = [i for i in range(batch_size)]
    run_through = False
    for i in range(iters):
        _, labels, time = pipe.run()
        labels = labels.as_cpu().as_array()
        time   = time.as_cpu().as_array()
        print(labels.flatten(), time.flatten())

        assert(len(set(int(label) for label in labels)) == len(labels))
        for k in range(batch_size):
            if labels[k] == last_labels[k]:
                # it is possible to restart a series hence time may be zero
                assert(time[k] == last_times[k] + sequence_length or time[k] == 0)

                # but it is not possible to restart all at once since the shorter
                # videos should repeat themself.
                if any(labels[j] != init_labels[j] for j in range(batch_size)):
                    assert(any(time[j] != 0 for j in range(batch_size)))
            elif run_through and all(labels[j] == init_labels[j] for j in range(batch_size)):
                assert(all(time[k] == 0 for k in range(batch_size)))

                # no need for further testing.
                del pipe
                return
            else:
                assert(labels[k] == last_labels[k] + batch_size)
                assert(time[k] == 0)

            # we can be sure that we run through the data once
            # if we got at least one label that belongs to
            # the last of the videos.
            run_through = True if labels[k] == end_labels[k] else run_through
            last_labels[k] = labels[k]
            last_times[k] = time[k]
    del pipe

def _test_clamp_continuous_interleave_mode(batch_size, sequence_length, iters):
    assert(len(VIDEO_FILES) % batch_size == 0)
    pipe = LabeledVideoPipe(batch_size=batch_size, data=VIDEO_FILES,
                            sequence_length=sequence_length,
                            interleave_size=batch_size,
                            interleave_mode="clamp_continuous",
                            shuffle=False)
    pipe.build()
    
    last_times  = [-sequence_length for _ in range(batch_size)]
    max_times   = [0 for _ in range(batch_size)]
    last_labels = [-batch_size + i  for i in range(batch_size)]
    end_labels = [len(VIDEO_FILES) - i - 1 for i in range(batch_size)]
    init_labels = [i for i in range(batch_size)]
    run_through = False
    for i in range(iters):
        _, labels, time = pipe.run()
        labels = labels.as_cpu().as_array()
        time   = time.as_cpu().as_array()
        print(labels.flatten(), time.flatten())

        assert(len(set(int(label) for label in labels)) == len(labels))
        for k in range(batch_size):
            if labels[k] == last_labels[k]:
                # it may be the end of a series hence the time may be equal to the last one
                assert(time[k] == last_times[k] + sequence_length or time[k] == max_times[k])

                # but it is not possible to restart all at once since the shorter
                # videos should repeat the last sequence.
                if any(labels[j] != init_labels[j] for j in range(batch_size)):
                    assert(any(time[j] != max_times[j] for j in range(batch_size)))
            elif run_through and all(labels[j] == init_labels[j] for j in range(batch_size)):
                assert(all(time[k] == 0 for k in range(batch_size)))

                # no need for further testing.
                del pipe
                return
            else:
                assert(labels[k] == last_labels[k] + batch_size)
                assert(time[k] == 0 or time[k] == max_times[k])
                max_times[k] = 0

            # we can be sure that we run through the data once
            # if we got at least one label that belongs to
            # the last of the videos.
            run_through = True if labels[k] == end_labels[k] else run_through
            last_labels[k] = labels[k]
            last_times[k] = time[k]
            max_times[k] = max(max_times[k], time[k])
    del pipe

def test_shorten_interleave_mode():
    _test_interleave_mode(_test_shorten_interleave_mode)

def test_repeat_interleave_mode():
    _test_interleave_mode(_test_repeat_interleave_mode)

def test_clamp_interleave_mode():
    _test_interleave_mode(_test_clamp_interleave_mode)

def test_shorten_continuous_interleave_mode():
    _test_continuous_interleave_mode(_test_shorten_continuous_interleave_mode)

def test_repeat_continuous_interleave_mode():
    _test_continuous_interleave_mode(_test_repeat_continuous_interleave_mode)

def test_clamp_continuous_interleave_mode():
    _test_continuous_interleave_mode(_test_clamp_continuous_interleave_mode)